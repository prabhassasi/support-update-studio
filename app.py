import base64
import io
import json
import os
import re
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel, Field
from streamlit_quill import st_quill

# ==========================================
# 1. LOCAL AUTH & PERSISTENT USER DATABASE
# ==========================================
USER_DB_FILE = "users.json"

def load_users() -> dict:
    """Loads user credentials from local JSON file."""
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_user(username: str, password_hash: str):
    """Saves a new user to the local JSON user database."""
    users = load_users()
    users[username] = password_hash
    with open(USER_DB_FILE, "w") as f:
        json.dump(users, f, indent=2)

def require_login():
    """Renders login/signup form and persists sessions across F5 reloads via query params."""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

    # Check for existing session token in URL query params to survive F5 refreshes
    if not st.session_state.logged_in:
        saved_user = st.query_params.get("user", None)
        users = load_users()
        if saved_user and saved_user in users:
            st.session_state.logged_in = True
            st.session_state.username = saved_user

    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            st.markdown("### 🔒 Support Update Studio")
            st.caption("Sign in to your account or create a new local user profile.")
            
            tab_login, tab_signup = st.tabs(["🔑 Sign In", "📝 Sign Up"])
            users = load_users()

            # --- TAB 1: SIGN IN ---
            with tab_login:
                if not users:
                    st.info("No registered users found. Switch to the **Sign Up** tab to create your account.")
                with st.form("local_login_form"):
                    username = st.text_input("Username", placeholder="e.g. admin or engineer")
                    password = st.text_input("Password", type="password")
                    submit = st.form_submit_button("Sign In", type="primary", use_container_width=True)

                    if submit:
                        clean_user = username.strip().lower()
                        if clean_user in users and users[clean_user] == password:
                            st.session_state.logged_in = True
                            st.session_state.username = clean_user
                            st.query_params["user"] = clean_user  # Persist across F5 reloads
                            st.toast(f"Welcome back, {clean_user}!", icon="👋")
                            st.rerun()
                        else:
                            st.error("Invalid username or password.")

            # --- TAB 2: SIGN UP ---
            with tab_signup:
                with st.form("local_signup_form"):
                    new_user = st.text_input("New Username", placeholder="e.g. admin")
                    new_pass = st.text_input("New Password", type="password")
                    confirm_pass = st.text_input("Confirm Password", type="password")
                    signup_submit = st.form_submit_button("Create Account", type="primary", use_container_width=True)

                    if signup_submit:
                        clean_user = new_user.strip().lower()
                        if not clean_user or not new_pass.strip():
                            st.error("Username and password cannot be empty.")
                        elif clean_user in users:
                            st.error("Username already exists. Please choose a different username.")
                        elif new_pass != confirm_pass:
                            st.error("Passwords do not match.")
                        else:
                            save_user(clean_user, new_pass)
                            st.success("Account created successfully! Switch to the 'Sign In' tab to log in.")
        st.stop()


# ==========================================
# 2. PAGE CONFIGURATION & CUSTOM CSS
# ==========================================
st.set_page_config(
    page_title="Support Update Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS_STYLES = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .header-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f766e 100%);
        padding: 24px 32px;
        border-radius: 16px;
        color: #ffffff;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .header-title {
        font-size: 26px;
        font-weight: 700;
        margin: 0;
        color: #ffffff;
    }
    .header-subtitle {
        font-size: 14px;
        color: #94a3b8;
        margin-top: 4px;
    }
    .version-badge {
        background: rgba(20, 184, 166, 0.2);
        border: 1px solid #14b8a6;
        color: #2dd4bf;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
    }

    div[data-baseweb="textarea"] textarea {
        font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace;
        font-size: 13.5px;
        border-radius: 8px;
    }
    
    .ql-container {
        min-height: 240px;
        font-size: 14px;
        border-bottom-left-radius: 8px;
        border-bottom-right-radius: 8px;
        background-color: #ffffff;
    }
    .ql-toolbar {
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        background-color: #f8fafc;
    }
</style>
"""
st.markdown(CSS_STYLES, unsafe_allow_html=True)

# Enforce local authentication gate
require_login()


# ==========================================
# 3. PARSER & STRICT MARKDOWN SANITIZER
# ==========================================
def parse_quill_content(html_content: str):
    """Extracts plain text and embedded base64 images from Quill HTML."""
    if not html_content:
        return "", None

    img_match = re.search(r'data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)', html_content)
    pil_image = None
    if img_match:
        base64_str = img_match.group(2)
        img_bytes = base64.b64decode(base64_str)
        pil_image = Image.open(io.BytesIO(img_bytes))

    text_only = re.sub(r'<img[^>]*>', '', html_content)
    text_only = re.sub(r'<br\s*/?>', '\n', text_only)
    text_only = re.sub(r'</p>', '\n', text_only)
    text_only = re.sub(r'<[^>]+>', '', text_only).strip()

    return text_only, pil_image


def sanitize_markdown(text: str) -> str:
    """Cleans up Markdown code blocks and enforces headers for Streamlit rendering."""
    if not text:
        return ""
    
    text = re.sub(r'^[ \t]+\x60\x60\x60', '\x60\x60\x60', text, flags=re.MULTILINE)
    
    headings = ["Summary", "What We Found", "Recommended Resolution", "Important Considerations", "Next Steps"]
    for heading in headings:
        pattern = rf'^(?:\*\*)?{heading}:?(?:\*\*)?'
        text = re.sub(pattern, f'\n\n### {heading}\n', text, flags=re.MULTILINE | re.IGNORECASE)

    text = re.sub(r'\x60\x60\x60[a-zA-Z]*\s*\x60\x60\x60', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ==========================================
# 4. SCHEMAS & SYSTEM INSTRUCTIONS
# ==========================================
class SupportDrafts(BaseModel):
    customer_update: str = Field(
        description="Comprehensive customer update formatted strictly with markdown headings: ### Summary, ### What We Found, ### Recommended Resolution, ### Important Considerations, ### Next Steps."
    )
    internal_case_note: str = Field(
        description="Detailed technical note formatted with: ## Environment, ## Observation, ## Analysis, ## References, ## Proposed resolution, ## Risks and checks, ## Next action."
    )
    escalation_summary: str = Field(
        description="Detailed escalation summary formatted with: ## Environment, ## Impact, ## Exact error, ## Evidence and analysis, ## Actions taken, ## Help needed."
    )

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_INSTRUCTION = """
You are a principal technical support engineer writing complete, detailed support drafts.

CRITICAL DIRECTIVES:
1. MANDATORY SPECIAL INSTRUCTIONS & LINKS: Any URLs, GitHub issues, PR numbers, or specific instructions provided in the 'Special Instructions' section MUST BE EXPLICITLY INCLUDED in the generated outputs (e.g., under 'What We Found', 'References', or 'Recommended Resolution'). Cite them directly in the text.
2. HEADINGS FORMATTING: Use explicit Markdown headings on their own lines (e.g., `### Summary`, `### What We Found`, `### Recommended Resolution`).
3. NO CODE BLOCKS INSIDE BULLETS: Place code blocks on top-level lines outside of bullet indentation.
4. EXHAUSTIVE TECHNICAL EVIDENCE: Preserve and output all raw terminal commands, node tables (`kubectl get nodes`), IP addresses, log lines, and exact error strings (like `websocket: bad handshake`).
5. NO INVENTED FACTS: Rely strictly on provided context and images.
"""

@st.cache_resource
def get_client(user_key: str = None):
    api_key = user_key if user_key and user_key.strip() else None
    
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
        
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY", None)
        except Exception:
            api_key = None

    if not api_key:
        raise RuntimeError(
            "Missing Gemini API Key. Paste your API key in the sidebar text box or set GEMINI_API_KEY in your environment."
        )

    return genai.Client(api_key=api_key)

def generate_all_drafts(
    case_title: str, 
    tone: str, 
    notes: str, 
    instruction: str, 
    pil_image=None,
    api_key_override: str = None
) -> SupportDrafts:
    client = get_client(api_key_override)
    
    user_prompt = f"""
Case Title: {case_title or 'N/A'}
Preferred Tone: {tone}

=== MANDATORY SPECIAL INSTRUCTIONS & REFERENCE LINKS ===
{instruction if instruction and instruction.strip() else 'None provided.'}
======================================================

--- TECHNICAL CASE NOTES & OUTPUTS ---
{notes or 'No written text notes provided. Refer to attached screenshot/image for full logs and command outputs.'}
--- END CASE NOTES ---

CRITICAL INSTRUCTION CHECK:
If text or a URL (such as a GitHub issue) is listed under "MANDATORY SPECIAL INSTRUCTIONS & REFERENCE LINKS" above, you MUST explicitly include and reference that exact URL/note in your drafts (e.g. under 'What We Found', 'References', or 'Recommended Resolution').

Generate three distinct, highly detailed drafts:
1. Customer Update
2. Internal Case Note
3. Escalation Summary
"""

    contents = [user_prompt]
    if pil_image is not None:
        contents.append(pil_image)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.15,
            response_mime_type="application/json",
            response_schema=SupportDrafts,
        ),
    )
    
    raw_drafts = SupportDrafts.model_validate_json(response.text)
    
    return SupportDrafts(
        customer_update=sanitize_markdown(raw_drafts.customer_update),
        internal_case_note=sanitize_markdown(raw_drafts.internal_case_note),
        escalation_summary=sanitize_markdown(raw_drafts.escalation_summary),
    )


# ==========================================
# 5. HEADER BANNER
# ==========================================
HEADER_HTML = """
<div class="header-banner">
    <div>
        <div class="header-title">⚡ Support Update Studio</div>
        <div class="header-subtitle">Transform unstructured case logs & screenshots into detailed, production-ready communications</div>
    </div>
    <div class="version-badge">Admin Directory • v3.9</div>
</div>
"""
st.markdown(HEADER_HTML, unsafe_allow_html=True)


# ==========================================
# 6. SIDEBAR CONFIGURATION & ACCOUNT INFO
# ==========================================
current_username = st.session_state.get("username", "Guest")
is_admin = current_username.lower() == "admin"

with st.sidebar:
    st.header("👤 User Account")
    st.write(f"Logged in as: **{current_username}** {'(Admin)' if is_admin else ''}")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Refresh", use_container_width=True, help="Reset all input fields and clear workspace outputs"):
            st.session_state.form_version = st.session_state.get("form_version", 0) + 1
            if "drafts" in st.session_state:
                del st.session_state["drafts"]
            st.rerun()
            
    with col_btn2:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            if "drafts" in st.session_state:
                del st.session_state["drafts"]
            st.query_params.clear()
            st.rerun()
        
    st.divider()
    st.header("⚙️ Configuration")
    
    user_api_key = st.text_input(
        "🔑 Gemini API Key",
        type="password",
        placeholder="Paste AIzaSy... here",
        help="Paste your API key here if not configured in the server environment."
    )
    
    tone = st.selectbox(
        "Communication Tone",
        ["🤝 Simple and Polite", "🛠️ Technical / Detailed", "⚡ Brief Status Update"],
        index=1
    )
    st.divider()
    st.subheader("🛡️ Data Security & Safety")
    st.warning("Do NOT enter passwords, API tokens, customer secrets, or unredacted support bundles.")
    st.divider()
    st.caption(f"🤖 Model Active: `{MODEL_NAME}`")


# ==========================================
# 7. MAIN WORKSPACE
# ==========================================
form_v = st.session_state.get("form_version", 0)

col_input, col_output = st.columns([1, 1.2], gap="large")

with col_input:
    st.subheader("📝 Case Inputs")
    
    case_title = st.text_input(
        "Case Title or Reference ID",
        placeholder="e.g., share-mnt down / node disconnect / restore required",
        key=f"case_title_{form_v}"
    )
    
    st.write("**Technical Case Notes & Screenshots** (Paste text or press `Ctrl + V` / `Cmd + V` to paste screenshots directly into this box)")
    
    quill_raw_content = st_quill(
        placeholder="Type/paste text logs or press Ctrl+V to paste a Snipping Tool screenshot directly into this editor...",
        html=True,
        key=f"quill_case_notes_{form_v}"
    )
    
    extracted_text, extracted_image = parse_quill_content(quill_raw_content)

    if extracted_image is not None:
        st.success("📸 Screenshot detected inside case notes!")
        st.image(extracted_image, caption="Extracted Screenshot Preview", use_container_width=True)

    drafting_instruction = st.text_area(
        "Special Instructions (Optional)",
        height=90,
        placeholder="e.g., Looks like this is the similar bug that you are facing: https://github.com/rancher/dashboard/issues/16626",
        key=f"drafting_instruction_{form_v}"
    )
    
    submit_btn = st.button("🚀 Generate All Drafts", type="primary", use_container_width=True)

    if submit_btn:
        if not extracted_text.strip() and extracted_image is None and not drafting_instruction.strip():
            st.error("Please enter technical notes, paste a screenshot, or provide special instructions.")
        else:
            try:
                with st.spinner("Processing context & generating structured drafts..."):
                    st.session_state.drafts = generate_all_drafts(
                        case_title, tone, extracted_text, drafting_instruction, extracted_image, user_api_key
                    )
                st.toast("Drafts generated successfully!", icon="✅")
            except Exception as exc:
                st.error(f"Generation failed: {exc}")


with col_output:
    st.subheader("📄 Workspace & Drafts")
    
    # Configure workspace tabs (Admin receives an extra 'Registered Users' tab)
    tab_titles = ["📨 Customer Update", "📋 Detailed Internal Note", "🔥 Escalation"]
    if is_admin:
        tab_titles.append("👥 Admin: Registered Users")

    tabs = st.tabs(tab_titles)
    
    # If Admin, render the user directory tab
    if is_admin:
        with tabs[3]:
            st.markdown("### 👥 Registered User Accounts")
            st.caption("Admin view of all users registered in `users.json`.")
            registered_users = load_users()
            if registered_users:
                user_list = [{"Username": u, "Account Type": "Administrator" if u == "admin" else "Standard User"} for u in registered_users.keys()]
                st.table(user_list)
            else:
                st.info("No registered users found in `users.json`.")

    if "drafts" in st.session_state:
        drafts: SupportDrafts = st.session_state.drafts
        
        def render_draft_tab(draft_text: str, key_prefix: str):
            view_mode = st.radio(
                "View Mode",
                ["🎨 Formatted Preview", "✏️ Raw Text / Copy"],
                horizontal=True,
                key=f"{key_prefix}_mode_{form_v}",
                label_visibility="collapsed"
            )

            html_content = draft_text
            html_content = re.sub(
                r'\x60\x60\x60(?:bash|text|json)?\n(.*?)\n\x60\x60\x60', 
                r'<pre style="background:#f8fafc; border:1px solid #cbd5e1; padding:10px; border-radius:6px; font-family:monospace; font-size:13px; color:#0f172a;">\1</pre>', 
                html_content, 
                flags=re.DOTALL
            )
            html_content = re.sub(r'^### (.*?)$', r'<h3 style="color:#0f172a; margin-top:16px; margin-bottom:8px; font-size:18px;">\1</h3>', html_content, flags=re.MULTILINE)
            html_content = re.sub(r'^## (.*?)$', r'<h2 style="color:#0f172a; margin-top:18px; margin-bottom:8px; font-size:20px;">\1</h2>', html_content, flags=re.MULTILINE)
            html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)
            html_content = re.sub(r'`([^`]+)`', r'<code style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-family:monospace; color:#0f172a;">\1</code>', html_content)
            
            parts = re.split(r'(<pre.*?>.*?</pre>)', html_content, flags=re.DOTALL)
            new_parts = []
            for part in parts:
                if part.startswith('<pre'):
                    new_parts.append(part)
                else:
                    new_parts.append(part.replace('\n', '<br>'))
            html_content = "".join(new_parts)

            js_text_payload = json.dumps(draft_text)

            copy_html = f"""
            <div style="display: flex; gap: 10px; margin-bottom: 12px;">
                <button id="richCopyBtn" onclick="copyRichText()" 
                        style="background-color: #0f766e; color: white; border: none; padding: 8px 16px; 
                               border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 13px;">
                    📋 Copy Formatted (Salesforce Rich Text)
                </button>
                <button id="rawCopyBtn" onclick="copyRawText()" 
                        style="background-color: #475569; color: white; border: none; padding: 8px 16px; 
                               border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 13px;">
                    📄 Copy Raw Markdown
                </button>
            </div>

            <div id="formattedTarget" style="display:none; font-family: sans-serif; color: #0f172a;">
                {html_content}
            </div>

            <script>
            function copyRichText() {{
                const target = document.getElementById('formattedTarget');
                target.style.display = 'block';
                const range = document.createRange();
                range.selectNode(target);
                window.getSelection().removeAllRanges();
                window.getSelection().addRange(range);
                
                try {{
                    document.execCommand('copy');
                    const btn = document.getElementById('richCopyBtn');
                    btn.innerText = '✅ Formatted Text Copied!';
                    btn.style.backgroundColor = '#15803d';
                    setTimeout(() => {{
                        btn.innerText = '📋 Copy Formatted (Salesforce Rich Text)';
                        btn.style.backgroundColor = '#0f766e';
                    }}, 2500);
                }} catch (err) {{
                    alert('Copy failed: ' + err);
                }} finally {{
                    target.style.display = 'none';
                    window.getSelection().removeAllRanges();
                }}
            }}

            function copyRawText() {{
                const text = {js_text_payload};
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                try {{
                    document.execCommand('copy');
                    const btn = document.getElementById('rawCopyBtn');
                    btn.innerText = '✅ Raw Markdown Copied!';
                    btn.style.backgroundColor = '#15803d';
                    setTimeout(() => {{
                        btn.innerText = '📄 Copy Raw Markdown';
                        btn.style.backgroundColor = '#475569';
                    }}, 2500);
                }} catch (err) {{
                    alert('Copy failed: ' + err);
                }} finally {{
                    document.body.removeChild(textarea);
                }}
            }}
            </script>
            """
            components.html(copy_html, height=52)

            if view_mode == "🎨 Formatted Preview":
                st.markdown(
                    f"""
                    <style>
                        .sf-preview code {{
                            background-color: #f1f5f9 !important;
                            color: #0f172a !important;
                            border: 1px solid #cbd5e1 !important;
                        }}
                        .sf-preview pre {{
                            background-color: #f8fafc !important;
                            border: 1px solid #cbd5e1 !important;
                            border-radius: 6px !important;
                        }}
                    </style>
                    <div class="sf-preview">
                    """,
                    unsafe_allow_html=True
                )
                st.markdown(draft_text)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.code(draft_text, language="markdown")

        with tabs[0]:
            render_draft_tab(drafts.customer_update, "cust")
        with tabs[1]:
            render_draft_tab(drafts.internal_case_note, "int")
        with tabs[2]:
            render_draft_tab(drafts.escalation_summary, "esc")
            
    else:
        st.info("👈 Fill in case details, paste a screenshot, or enter special instructions on the left and click **Generate All Drafts**.")
