import re
import json

def clean_text(text):
    """Clean raw HTML and special characters from webpage content."""
    text = re.sub(r'<[^>]*?>', '', text)  # Remove HTML tags
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)  # Remove URLs
    text = re.sub(r'[^a-zA-Z0-9 ]', '', text)  # Remove non-alphanum characters
    text = re.sub(r'\s{2,}', ' ', text)  # Collapse multiple spaces
    text = text.strip()
    text = ' '.join(text.split())  # Remove excess whitespace
    return text

def extract_jobs_summary(job):
    """Format job summary with new lines and bullet points."""
    role = job.get("role", "Unknown Role")
    experience = job.get("experience", "N/A")
    skills = job.get("skills", [])
    description = job.get("description", "N/A")

    skills_formatted = "\n".join([f"- {s}" for s in skills])

    summary = (
        f"Role: {role}\n"
        f"Experience: {experience}\n"
        f"Skills:\n{skills_formatted}\n"
        f"Description: {description}"
    )
    return summary