import os
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from dotenv import load_dotenv
import re
import json
from typing import List, Dict, Any

load_dotenv()

class Chain:
    def __init__(self):
        self.llm = ChatGroq(temperature=0.7, groq_api_key=os.getenv("GROQ_API_KEY"), model_name="llama-3.1-8b-instant")
        self.max_chunk_size = 8000  # Characters per chunk

    def extract_jobs(self, cleaned_text):
        """
        Extract job postings from scraped text, with chunking for large texts.
        Returns a list of job dictionaries.
        """
        # If text is small enough, process directly
        if len(cleaned_text) < self.max_chunk_size:
            return self._process_job_chunk(cleaned_text)
        
        # For larger text, chunk it and process each chunk
        chunks = self._chunk_text(cleaned_text)
        
        # Process each chunk and collect results
        all_jobs = []
        for i, chunk in enumerate(chunks):
            try:
                chunk_jobs = self._process_job_chunk(chunk)
                if chunk_jobs:
                    all_jobs.extend(chunk_jobs if isinstance(chunk_jobs, list) else [chunk_jobs])
            except Exception as e:
                print(f"Error processing chunk {i+1}: {str(e)}")
        
        # De-duplicate jobs based on role names
        return self._deduplicate_jobs(all_jobs)
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into smaller chunks with potential job overlap."""
        chunks = []
        # Use regex to find potential job section indicators
        job_patterns = r"(job|position|role|opening|career|opportunity)"
        
        # Find all potential job section starts
        job_indices = [m.start() for m in re.finditer(job_patterns, text, re.IGNORECASE)]
        job_indices = [0] + job_indices + [len(text)]
        job_indices = sorted(list(set(job_indices)))  # Remove duplicates and sort
        
        # Create chunks with overlap between potential job sections
        for i in range(len(job_indices) - 1):
            chunk_start = max(0, job_indices[i] - 200)  # Include some context before
            
            # Calculate end to not exceed max chunk size
            chunk_end = min(job_indices[i] + self.max_chunk_size, len(text))
            if i+1 < len(job_indices):
                chunk_end = min(chunk_end, job_indices[i+1] + 500)  # Include overlap
            
            chunks.append(text[chunk_start:chunk_end])
            
            # Skip ahead if we've already covered text in our chunk
            if i+1 < len(job_indices) and job_indices[i+1] < chunk_end - 200:
                continue
        
        # Ensure we don't have too many chunks
        if len(chunks) > 5:
            # Combine chunks to avoid having too many
            new_chunks = []
            for i in range(0, len(chunks), 2):
                if i+1 < len(chunks):
                    new_chunks.append(chunks[i] + " " + chunks[i+1])
                else:
                    new_chunks.append(chunks[i])
            chunks = new_chunks
            
        # If we still don't have any chunks (rare case), create evenly sized chunks
        if not chunks:
            chunk_size = self.max_chunk_size - 500  # Leave room for overlap
            for i in range(0, len(text), chunk_size):
                chunks.append(text[i:i + chunk_size])
        
        return chunks

    def _process_job_chunk(self, chunk_text: str) -> List[Dict[str, Any]]:
        """Process a single text chunk to extract job information."""
        prompt_extract = PromptTemplate.from_template(
            """
            ### SCRAPED TEXT FROM WEBSITE:
            {page_data}
            ### INSTRUCTION:
            The scraped text is from the career's page of a website.
            Your job is to extract the job postings and return them in JSON format containing the following keys: `role`, `experience`, `skills` and `description`.
            If multiple jobs are found, return an array of job objects.
            If no jobs are found, return an empty array.
            Only return the valid JSON with no additional text.
            ### VALID JSON ARRAY (NO PREAMBLE):
            """
        )
        chain_extract = prompt_extract | self.llm
        res = chain_extract.invoke(input={"page_data": chunk_text})
        
        try:
            json_parser = JsonOutputParser()
            parsed_result = json_parser.parse(res.content)
            
            # Ensure we always return a list
            if isinstance(parsed_result, dict):
                return [parsed_result]
            elif isinstance(parsed_result, list):
                return parsed_result
            else:
                return []
        except OutputParserException as e:
            # Try to extract JSON from the response using regex
            try:
                json_matches = re.findall(r'(\[.*\]|\{.*\})', res.content, re.DOTALL)
                if json_matches:
                    for match in json_matches:
                        try:
                            parsed = json.loads(match)
                            if isinstance(parsed, dict):
                                return [parsed]
                            elif isinstance(parsed, list):
                                return parsed
                        except:
                            continue
            except:
                pass
                
            # If all attempts fail, return empty list
            print(f"Error parsing output: {str(e)}")
            return []

    def _deduplicate_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate jobs based on role name and description similarity."""
        if not jobs:
            return []
        
        # Create a dictionary with role as key to identify duplicates
        unique_jobs = {}
        
        for job in jobs:
            role = job.get('role', '').strip().lower()
            desc = job.get('description', '').strip().lower()
            
            # Skip empty roles
            if not role:
                continue
                
            # Create a simple hash for the job using first 100 chars of description
            job_hash = f"{role}_{desc[:100] if desc else ''}"
            
            # If this is a new job or has a more complete entry than existing
            if job_hash not in unique_jobs or \
               len(job.get('description', '')) > len(unique_jobs[job_hash].get('description', '')) or \
               len(job.get('skills', [])) > len(unique_jobs[job_hash].get('skills', [])):
                unique_jobs[job_hash] = job
        
        return list(unique_jobs.values())

    def write_mail(self, job, links, tone="Professional", variant_id=1, user_name="Mohan", company_name="AtliQ", summary="", benefits=""):
        prompt_email = PromptTemplate.from_template(
            """
            ### JOB DESCRIPTION:
            {job_description}

            ### INSTRUCTION:
            You are {user_name}, a business development executive at {company_name}. {summary}
            Your job is to write a cold email to the client regarding the job mentioned above describing how your company can fulfill their needs.
            Mention these key advantages: {benefits}
            Use a {tone} tone.
            This is version #{variant_id}, try phrasing it slightly differently.
            Also add the most relevant ones from the following links to showcase your portfolio: {link_list}
            Do not provide a preamble.
            ### EMAIL (NO PREAMBLE):
            """
        )
        chain_email = prompt_email | self.llm
        res = chain_email.invoke({
            "job_description": str(job),
            "link_list": links,
            "tone": tone,
            "variant_id": variant_id,
            "user_name": user_name,
            "company_name": company_name,
            "summary": summary,
            "benefits": benefits
        })
        return res.content