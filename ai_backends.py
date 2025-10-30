import os
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai

# Load environment variables
load_dotenv()

# OpenAI client
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = None
if OPENAI_KEY:
    try:
        client = OpenAI(api_key=OPENAI_KEY)
    except Exception:
        client = None

# Gemini setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        pass


def get_chatgpt_response(query, context):
    """Call OpenAI (modern client). Returns string or raises Exception."""
    if client is None:
        raise RuntimeError("OpenAI client not configured")

    system_message = (
        "You are a specialized AI assistant for a Quantum Protein Folding Dashboard.\n"
        f"Current context:\n- Protein Sequence: {context.get('current_protein', 'None')}\n"
        f"- VQE Results: {context.get('vqe_results', 'None')}\n"
        f"- Last Analysis: {context.get('last_analysis', 'None')}\n\n"
        "Focus on quantum computing concepts (VQE, quantum circuits, qubits), protein folding mechanisms,"
        " and current simulation results. Keep responses clear and technical."
    )

    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": system_message}, {"role": "user", "content": query}],
        temperature=0.7,
        max_tokens=500,
    )

    # extract
    try:
        choice = resp.choices[0]
        msg = getattr(choice, "message", None) or (choice.get("message") if isinstance(choice, dict) else None)
        if isinstance(msg, dict):
            return msg.get("content") or ""
        return getattr(msg, "content", str(choice))
    except Exception:
        return str(resp)


def get_gemini_response(query, context, model="models/gemini-2.5-flash"):
    """Call Google's Generative AI using the official client library."""
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini API key not configured")

    # Format context for model
    context_str = "\n".join([
        f"Current context:",
        f"- Protein Sequence: {context.get('current_protein', 'None')}",
        f"- VQE Results: {context.get('vqe_results', 'None')}",
        f"- Last Analysis: {context.get('last_analysis', 'None')}\n",
        "Instructions: Focus on quantum computing concepts (VQE, quantum circuits, qubits), protein folding mechanisms, and current simulation results. Keep responses clear and technical.\n",
        f"User query: {query}"
    ])

    try:
        model_client = genai.GenerativeModel(model)
        response = model_client.generate_content(context_str)
        if hasattr(response, 'text'):
            return response.text
        return str(response)
    except Exception as e:
        # Try a known-working flash/latest fallback model if initial fails
        try:
            fallback_model = "models/gemini-flash-latest"
            if model != fallback_model:
                fb_client = genai.GenerativeModel(fallback_model)
                fb_resp = fb_client.generate_content(context_str)
                if hasattr(fb_resp, 'text'):
                    return fb_resp.text
                return str(fb_resp)
        except Exception:
            pass
        raise RuntimeError(f"Gemini error: {str(e)}")


def local_kb_response(query, context):
    q = query.lower()
    if 'vqe' in q or 'variational' in q:
        return (
            "VQE (Variational Quantum Eigensolver) is a hybrid quantum-classical algorithm that optimizes a parameterized quantum circuit "
            "to approximate the ground state of a Hamiltonian. It uses a classical optimizer to update circuit parameters."
        )
    if 'protein' in q or 'fold' in q or 'structure' in q:
        current = context.get('current_protein') or 'no sequence loaded'
        if current and current != 'None' and current != 'no sequence loaded':
            return f"Currently loaded protein (preview): {current}. Protein folding depends on sequence interactions and environment."
        return (
            "Protein folding is the process by which an amino acid chain adopts its 3D shape; it's driven by interactions between residues and the solvent."
        )
    if 'quantum' in q or 'qubit' in q or 'entanglement' in q:
        return (
            "Quantum computing leverages superposition and entanglement to perform computations that are hard for classical machines; qubits are the basic unit."
        )
    return (
        "I don't have an external API connection right now; try asking about 'VQE', 'protein folding', or 'quantum computing'."
    )


def get_response(model_choice, query, context):
    """Unified response function: tries chosen model or falls back.
    model_choice: string, e.g., 'ChatGPT (OpenAI)' or 'Gemini (Google)'
    """
    # Route based on explicit choice
    if model_choice and 'gemini' in model_choice.lower():
        try:
            return get_gemini_response(query, context)
        except Exception as e:
            # fallback to local
            return f"Gemini error: {e}\n\n{local_kb_response(query, context)}"

    if model_choice and 'chatgpt' in model_choice.lower():
        try:
            return get_chatgpt_response(query, context)
        except Exception as e:
            # try gemini then local
            try:
                return get_gemini_response(query, context)
            except Exception:
                return f"OpenAI error: {e}\n\n{local_kb_response(query, context)}"

    # Default: try OpenAI, then Gemini, then local
    try:
        # Default to Gemini (it's faster and has better latency)
        return get_gemini_response(query, context)
    except Exception as e1:
        # If Gemini fails, try OpenAI
        try:
            return get_chatgpt_response(query, context)
        except Exception as e2:
            # Enhanced error reporting in local fallback
            if "quota" in str(e1).lower() or "429" in str(e1):
                prefix = "Gemini API quota exceeded. "
            elif "400" in str(e1):
                prefix = "Gemini API configuration error (check key permissions). "
            else:
                prefix = f"API error ({str(e1)[:100]}). "
            
            return prefix + local_kb_response(query, context)
