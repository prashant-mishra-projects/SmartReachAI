import streamlit as st
from langchain_community.document_loaders import WebBaseLoader
from chains import Chain
from portfolio import Portfolio
from utils import clean_text, extract_jobs_summary
import pandas as pd
import os
from datetime import datetime
import traceback
import requests
from bs4 import BeautifulSoup

EMAIL_HISTORY_PATH = "email_history.csv"

# Set page configuration and theme
st.set_page_config(
    layout="wide",
    page_title="SmartReachAI",
    page_icon="📧",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme styling
def load_css():
    st.markdown("""
    <style>
        /* General dark theme */
        .stApp {
            background-color: #121212;
            color: #E0E0E0;
        }
        
        /* Headers */
        .main-header {
            font-size: 42px;
            font-weight: bold;
            color: #42A5F5;
            margin-bottom: 20px;
        }
        .sub-header {
            font-size: 26px;
            font-weight: bold;
            color: #64B5F6;
            margin-top: 30px;
            margin-bottom: 15px;
        }
        
        /* Cards */
        .card {
            background-color: #1E1E1E;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            margin-bottom: 20px;
            border: 1px solid #333;
        }
        
        /* Email variant styling */
        .email-variant {
            background-color: #1A237E;
            padding: 10px;
            border-radius: 5px;
            border-left: 5px solid #42A5F5;
            margin-bottom: 15px;
            color: #E0E0E0;
        }
        
        /* Sidebar */
        .sidebar-header {
            font-size: 20px;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 10px;
            color: #64B5F6;
        }
        
        /* Buttons */
        .stButton button {
            background-color: #1976D2 !important;
            color: white !important;
            font-weight: bold !important;
            border-radius: 5px !important;
            border: none !important;
            padding: 8px 16px !important;
            min-width: 160px;
        }
        .stButton button:hover {
            background-color: #1565C0 !important;
        }
        
        /* Badge */
        .badge {
            background-color: #388E3C;
            color: white;
            padding: 3px 10px;
            border-radius: 30px;
            font-size: 14px;
            font-weight: bold;
        }
        
        /* Download button */
        .download-btn {
            text-align: right;
            margin-top: 10px;
        }
        
        /* Input fields */
        div[data-baseweb="input"] > div {
            background-color: #2C2C2C !important;
            border-color: #444 !important;
        }
        div[data-baseweb="input"] input {
            color: #E0E0E0 !important;
        }
        
        /* Override Streamlit elements */
        .stTextInput label, .stTextArea label, .stSelectbox label {
            color: #90CAF9 !important;
        }
        .stExpander {
            background-color: #1E1E1E !important;
            border: 1px solid #333 !important;
        }
        .stExpander summary {
            color: #90CAF9 !important;
        }
        
        /* Code blocks */
        pre {
            background-color: #212121 !important;
            border: 1px solid #444 !important;
        }
        code {
            color: #E0E0E0 !important;
        }
        
        /* Horizontal divider */
        hr {
            border-color: #444 !important;
        }
        
        /* Custom container for button alignment */
        .button-container {
            display: flex;
            justify-content: flex-end;
            margin-top: 15px;
        }
        
        /* Error message styling */
        .error-container {
            background-color: #421717;
            border-left: 5px solid #CF6679;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            color: #FFCDD2;
        }
        
        /* Info message styling */
        .info-container {
            background-color: #0d2647;
            border-left: 5px solid #64B5F6;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }
        
        /* Progress bar */
        .stProgress > div > div {
            background-color: #1976D2 !important;
        }
    </style>
    """, unsafe_allow_html=True)

def save_email_history(job, email):
    df = pd.DataFrame([{
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "role": job.get("role", "N/A"),
        "experience": job.get("experience", "N/A"),
        "skills": ", ".join(job.get("skills", [])),
        "email": email
    }])
    if os.path.exists(EMAIL_HISTORY_PATH):
        df.to_csv(EMAIL_HISTORY_PATH, mode='a', header=False, index=False)
    else:
        df.to_csv(EMAIL_HISTORY_PATH, index=False)

def display_job_card(job, index):
    with st.container():
        st.markdown(f"""
        <div class="card">
            <h3>{job.get('role', 'Unknown Role')} <span class="badge">Job #{index+1}</span></h3>
            <p><strong>Experience:</strong> {job.get('experience', 'N/A')}</p>
            <p><strong>Skills:</strong> {', '.join(job.get('skills', []))}</p>
            <details>
                <summary>View Description</summary>
                <p>{job.get('description', 'N/A')}</p>
            </details>
        </div>
        """, unsafe_allow_html=True)
        return st.checkbox(f"✅ Select this job", key=f"select_{index}")

def display_email_variant(email, job, variant_num, tone, export_enabled):
    with st.container():
        st.markdown(f"""
        <div class="email-variant">
            <h4>✉️ Email Variant {variant_num} - {tone} Tone</h4>
        </div>
        """, unsafe_allow_html=True)
        st.code(email, language='markdown')
        
        col1, col2 = st.columns([4, 1])
        with col2:
            st.download_button(
                "📥 Download Email", 
                data=email, 
                file_name=f"email_{job.get('role', 'job').replace(' ', '_')}_{variant_num}.md",
                use_container_width=True
            )
        
        if export_enabled:
            save_email_history(job, email)

def fetch_text_safely(url):
    """Safely fetch text from a URL with better error handling."""
    try:
        # First try with requests + Beautiful Soup for better HTML handling
        response = requests.get(url, timeout=15)
        response.raise_for_status()  # Raise exception for 4XX/5XX status codes
        
        # Use Beautiful Soup to extract text content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav']):
            script_or_style.extract()
            
        # Get text content
        page_text = soup.get_text(separator=' ', strip=True)
        
        # If the content is too small, we might not have gotten everything, so try LangChain's loader
        if len(page_text) < 1000:
            loader = WebBaseLoader([url])
            docs = loader.load()
            if docs:
                page_text = docs[0].page_content
                
        return page_text, None
        
    except requests.exceptions.RequestException as e:
        return None, f"Failed to access URL: {str(e)}"
    except Exception as e:
        try:
            # Fallback to LangChain's WebBaseLoader if requests+BS4 fails
            loader = WebBaseLoader([url])
            docs = loader.load()
            if docs:
                return docs[0].page_content, None
            else:
                return None, "Failed to extract content from the URL"
        except Exception as fallback_e:
            return None, f"Error fetching URL content: {str(fallback_e)}"

def create_streamlit_app(llm, portfolio, clean_text):
    load_css()
    
    # App Header
    st.markdown('<div class="main-header">📧 SmartReachAI</div>', unsafe_allow_html=True)
    st.markdown("Generate tailored outreach emails based on job postings")
    
    # Setup sidebar
    with st.sidebar:
        st.markdown('<div class="sidebar-header">⚙️ Configuration</div>', unsafe_allow_html=True)
        
        st.markdown("### Email Style")
        email_tone = st.selectbox("Tone", ["Professional", "Friendly", "Casual", "Enthusiastic", "Formal"])
        variant_count = st.slider("Number of Variants", 1, 5, 2)
        export_enabled = st.checkbox("Save to Email History", value=True)
        
        st.markdown('<div class="sidebar-header">🏢 Company Information</div>', unsafe_allow_html=True)
        user_name = st.text_input("Your Name", value="Prashant")
        company_name = st.text_input("Company Name", value="BLUME")
        
        with st.expander("Company Details"):
            company_summary = st.text_area(
                "Company Summary", 
                value="We are an AI & Software Consulting company dedicated to streamlining businesses through automation.",
                height=100
            )
            company_benefits = st.text_area(
                "Key Benefits", 
                value="Scalability, process optimization, cost reduction, efficiency.",
                height=100
            )
        
        st.markdown('<div class="sidebar-header">📊 Analytics</div>', unsafe_allow_html=True)
        if os.path.exists(EMAIL_HISTORY_PATH):
            if st.button("View Email History"):
                history = pd.read_csv(EMAIL_HISTORY_PATH)
                st.dataframe(
                    history[["date", "role"]],
                    column_config={"date": "Date", "role": "Job Role"},
                    hide_index=True
                )

        # Advanced Options
        st.markdown('<div class="sidebar-header">🔧 Advanced</div>', unsafe_allow_html=True)
        with st.expander("Debug Options"):
            debug_mode = st.checkbox("Enable Debug Mode", value=False)

    # Main content area
    if "submitted" not in st.session_state:
        st.session_state["submitted"] = False
    if "jobs" not in st.session_state:
        st.session_state["jobs"] = []
    if "loading" not in st.session_state:
        st.session_state["loading"] = False
    if "error" not in st.session_state:
        st.session_state["error"] = None

    # URL Input Section
    st.markdown('<div class="sub-header">🔍 Find Job Postings</div>', unsafe_allow_html=True)
    
    # URL input and button in proper alignment
    url_input = st.text_input("Enter a Job Post URL:", placeholder="https://example.com/jobs/software-engineer")
    
    # Button alignment container
    st.markdown('<div class="button-container" id="scrape-button-container"></div>', unsafe_allow_html=True)
    scrape_button = st.button("🔍 Scrape & Extract", key="scrape_btn")
    
    # Show error message if there was one from a previous attempt
    if st.session_state.get("error"):
        st.markdown(f"""
        <div class="error-container">
            <h4>⚠️ An Error Occurred</h4>
            <p>{st.session_state["error"]}</p>
            <p>For troubleshooting, visit: <a href="https://python.langchain.com/docs/troubleshooting/errors/OUTPUT_PARSING_FAILURE" target="_blank" style="color: #90CAF9;">LangChain Troubleshooting</a></p>
        </div>
        """, unsafe_allow_html=True)
    
    if scrape_button:
        if not url_input:
            st.error("Please enter a valid URL")
        else:
            st.session_state["loading"] = True
            st.session_state["error"] = None  # Reset any previous errors
            
            # Create a progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Step 1: Fetch the content
                status_text.text("Step 1/3: Fetching page content...")
                progress_bar.progress(10)
                
                content, fetch_error = fetch_text_safely(url_input)
                if fetch_error:
                    st.session_state["error"] = fetch_error
                    st.session_state["loading"] = False
                    st.experimental_rerun()
                    
                progress_bar.progress(40)
                status_text.text("Step 2/3: Cleaning and processing text...")
                
                # Step 2: Clean the content
                cleaned_data = clean_text(content)
                
                if debug_mode:
                    st.markdown(f"""
                    <div class="info-container">
                        <h4>Debug Info: Content Length</h4>
                        <p>Raw content length: {len(content)} characters</p>
                        <p>Cleaned content length: {len(cleaned_data)} characters</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                progress_bar.progress(60)
                status_text.text("Step 3/3: Extracting job information...")
                
                # Step 3: Load portfolio and extract jobs
                portfolio.load_portfolio()
                jobs = llm.extract_jobs(cleaned_data)
                
                # Update session state
                st.session_state["jobs"] = jobs
                st.session_state["submitted"] = True if jobs else False
                
                if not jobs:
                    st.session_state["error"] = "No jobs found in the provided URL. The page might not contain job listings or the format might not be recognized."
                
                progress_bar.progress(100)
                status_text.text("Processing complete!")
                
            except Exception as e:
                # Capture and show the full stack trace in debug mode
                if debug_mode:
                    st.session_state["error"] = f"Error details: {str(e)}\n\nStack trace: {traceback.format_exc()}"
                else:
                    if "Context too big" in str(e):
                        st.session_state["error"] = "Context too big. Unable to parse jobs. The page content is too large to process at once."
                    else:
                        st.session_state["error"] = f"An error occurred: {str(e)}"
                
            finally:
                st.session_state["loading"] = False
                # Remove progress elements after completion
                progress_bar.empty()
                status_text.empty()
                st.experimental_rerun()

    # Display Jobs Section
    if st.session_state["submitted"]:
        jobs = st.session_state["jobs"]
        
        st.markdown('<div class="sub-header">🧾 Available Job Positions</div>', unsafe_allow_html=True)
        if not jobs:
            st.info("No jobs were found on the provided URL. Try a different job posting page.")
        else:
            st.success(f"Found {len(jobs)} job postings")
            
            selected_jobs = []
            cols = st.columns(min(3, len(jobs)))
            
            for i, job in enumerate(jobs):
                with cols[i % min(3, len(jobs))]:
                    if display_job_card(job, i):
                        selected_jobs.append(job)
            
            # Email Generation Section
            if selected_jobs:
                st.markdown('<div class="sub-header">✉️ Generated Emails</div>', unsafe_allow_html=True)
                
                for job_idx, job in enumerate(selected_jobs):
                    st.markdown(f"### 📝 Emails for: {job.get('role', 'Job Position')}")
                    
                    skills = job.get('skills', [])
                    links = portfolio.query_links(skills)
                    
                    with st.spinner(f"Generating email variants..."):
                        for i in range(variant_count):
                            try:
                                email = llm.write_mail(
                                    job, links, 
                                    tone=email_tone, 
                                    variant_id=i+1,
                                    user_name=user_name, 
                                    company_name=company_name,
                                    summary=company_summary, 
                                    benefits=company_benefits
                                )
                                display_email_variant(email, job, i+1, email_tone, export_enabled)
                            except Exception as e:
                                st.error(f"Failed to generate email variant {i+1}: {str(e)}")
                    
                    if job_idx < len(selected_jobs) - 1:
                        st.markdown("---")
            else:
                st.warning("Select at least one job to generate emails.")

    # Quick Guide Section at the bottom
    with st.expander("ℹ️ How to use SmartReachAI"):
        st.markdown("""
        1. **Enter a job posting URL** in the text field above
        2. **Click 'Scrape & Extract'** to analyze the page
        3. **Select the jobs** you want to create emails for
        4. **Customize the email style** using the sidebar options
        5. **Download** the generated emails or save them to your history
        
        **Troubleshooting Tips:**
        - If you encounter "Context too big" errors, try using a more specific URL that points directly to a job posting rather than a list of many jobs
        - Make sure the URL is accessible and contains job descriptions in text format (not images)
        - Some websites with complex JavaScript may not be fully parsed - in that case, try copying the job text directly
        """)

if __name__ == "__main__":
    chain = Chain()
    portfolio = Portfolio()
    create_streamlit_app(chain, portfolio, clean_text)
