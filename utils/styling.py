"""
Styling utilities for the Streamlit application.
Contains CSS styling definitions and helper functions.
"""

def get_arial_font_css() -> str:
    return """
    <style>
        /* Keep Material Symbols for Streamlit icons (sidebar toggle, etc.) */
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0');

        /* App text uses Arial, but don't clobber icon fonts */
        .stApp,
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp p, .stApp div, .stApp label,
        .stTextInput input, .stTextArea textarea,
        .stButton button, .stDownloadButton button,
        .stSelectbox select, .stSelectbox label,
        .stMetric label, .stMetric [data-testid="metric-value"], .stMetric [data-testid="metric-delta"],
        .stAlert div, .streamlit-expanderContent p, .streamlit-expanderContent span,
        .stMarkdown, .stText, .stCode, .stLatex, .stCaption, .caption {
            font-family: Arial, Helvetica, sans-serif !important;
        }

        span[class*="material-icons"],
        span[class*="material-symbols"],
        [data-testid="baseButton-toggleSidebar"] span {
            font-family: 'Material Symbols Rounded','Material Icons','Material Symbols Outlined' !important;
            font-variation-settings: 'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;
        }

        /* --- Footer --- */
        .feedback-footer {
            position: fixed;
            left: 0;
            right: 0;
            bottom: 0;
            background: #f8f9fa;
            border-top: 1px solid #e9ecef;
            padding: 10px 20px;
            text-align: center;
            font-family: Arial, Helvetica, sans-serif !important;
            font-size: 14px;
            z-index: 99999; /* ensure it's above Streamlit UI */
            box-shadow: 0 -2px 10px rgba(0,0,0,0.08);
        }
        .feedback-footer a { color: #1f77b4; text-decoration: none; font-weight: 600; }
        .feedback-footer a:hover { text-decoration: underline; }

        /* Prevent overlap with fixed footer */
        [data-testid="stAppViewContainer"] > .main { padding-bottom: 64px; }
    </style>
    """



def add_custom_sidebar_toggle():
    """
    Add a custom sidebar toggle button to replace the problematic default one.
    """
    import streamlit as st
    
    toggle_html = """
    <div class="custom-sidebar-toggle" onclick="toggleSidebar()">
        ☰ Menu
    </div>
    
    <script>
    function toggleSidebar() {
        // Find and click the actual Streamlit sidebar toggle
        const sidebarToggle = document.querySelector('[data-testid="collapsedControl"], .stSidebar button[kind="header"]');
        if (sidebarToggle) {
            sidebarToggle.click();
        }
    }
    </script>
    """
    st.markdown(toggle_html, unsafe_allow_html=True)



def apply_custom_styling():
    """
    Apply custom styling to the Streamlit app.
    This function should be called early in the Streamlit app initialization.
    """
    import streamlit as st
    
    # Apply Arial font styling
    st.markdown(get_arial_font_css(), unsafe_allow_html=True)
