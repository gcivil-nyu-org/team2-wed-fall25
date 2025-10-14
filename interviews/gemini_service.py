"""
Gemini AI service for resume analysis and interview preparation.
"""
import google.generativeai as genai
from django.conf import settings
from PyPDF2 import PdfReader
import io
import json
import logging

logger = logging.getLogger(__name__)


class GeminiAnalyzer:
    """Service class for Gemini AI-powered resume analysis and interview generation"""
    
    def __init__(self):
        """Initialize Gemini AI with API key"""
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        else:
            self.model = None
    
    def extract_text_from_pdf(self, resume_file):
        """
        Extract text content from a PDF resume file.
        
        Args:
            resume_file: Django FieldFile object or file-like object
            
        Returns:
            str: Extracted text content
        """
        try:
            # Read the PDF file
            if hasattr(resume_file, 'read'):
                pdf_content = resume_file.read()
                resume_file.seek(0)  # Reset file pointer
            else:
                with open(resume_file, 'rb') as f:
                    pdf_content = f.read()
            
            # Create PDF reader
            pdf_reader = PdfReader(io.BytesIO(pdf_content))
            
            # Extract text from all pages
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text.strip()
        except Exception as e:
            return f"Error extracting text from PDF: {str(e)}"
    
    def analyze_resume_fit(self, resume_text, job_description, company_name):
        """
        Analyze how well a resume fits a job description using Gemini AI.
        
        Args:
            resume_text (str): The extracted resume text
            job_description (str): The job description to compare against
            company_name (str): The company name for context
            
        Returns:
            dict: Contains 'fit_score' (int 0-100), 'analysis' (str), 'suggestions' (str)
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                'fit_score': 0,
                'analysis': 'Gemini API key is not configured. Please add GEMINI_API_KEY to your environment variables.',
                'suggestions': 'Configure the API key to enable AI-powered resume analysis.'
            }
        
        try:
            # Create the prompt for Gemini
            prompt = f"""
You are an expert technical recruiter analyzing a candidate's resume for a position at {company_name}.

Job Description:
{job_description}

Candidate's Resume:
{resume_text}

Please provide a comprehensive analysis with the following:

1. **Fit Score**: Rate how well this resume matches the job description on a scale of 0-100. Just provide the number.

2. **Detailed Analysis**: Provide a thorough analysis (3-4 paragraphs) covering:
   - Key strengths and relevant experiences
   - How well the candidate's skills align with job requirements
   - Notable achievements and qualifications
   - Areas where the candidate excels for this role

3. **Improvement Suggestions**: Provide 5-7 specific, actionable suggestions to improve the resume for this position. Format as a bulleted list. Each suggestion should be concrete and implementable.

Format your response EXACTLY as follows:
FIT_SCORE: [number 0-100]

ANALYSIS:
[Your detailed analysis here]

SUGGESTIONS:
- [Suggestion 1]
- [Suggestion 2]
- [Suggestion 3]
...
"""
            
            # Call Gemini API
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Parse the response
            fit_score = 0
            analysis = ""
            suggestions = ""
            
            # Extract fit score
            if "FIT_SCORE:" in response_text:
                score_line = response_text.split("FIT_SCORE:")[1].split("\n")[0].strip()
                try:
                    fit_score = int(''.join(filter(str.isdigit, score_line)))
                    fit_score = max(0, min(100, fit_score))  # Ensure 0-100 range
                except:
                    fit_score = 50  # Default if parsing fails
            
            # Extract analysis
            if "ANALYSIS:" in response_text and "SUGGESTIONS:" in response_text:
                analysis = response_text.split("ANALYSIS:")[1].split("SUGGESTIONS:")[0].strip()
            elif "ANALYSIS:" in response_text:
                analysis = response_text.split("ANALYSIS:")[1].strip()
            
            # Extract suggestions
            if "SUGGESTIONS:" in response_text:
                suggestions = response_text.split("SUGGESTIONS:")[1].strip()
            
            # Fallback if parsing fails
            if not analysis:
                analysis = response_text
            
            return {
                'fit_score': fit_score,
                'analysis': analysis,
                'suggestions': suggestions
            }
            
        except Exception as e:
            return {
                'fit_score': 0,
                'analysis': f'An error occurred while analyzing the resume: {str(e)}',
                'suggestions': 'Please try again later or check your API configuration.'
            }
    
    def select_and_generate_questions(self, chunks, company_name, num_questions=2):
        """
        Select best question from chunks and generate similar coding questions.
        Gemini does the intelligent selection and generation.
        
        Args:
            chunks (list[str]): List of text chunks from company documents
            company_name (str): Company name for context
            num_questions (int): Number of questions to generate
            
        Returns:
            list[dict]: List of dicts with 'question' and 'solution' keys
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return [{
                'question': 'Error: Gemini API not configured',
                'solution': 'Please configure GEMINI_API_KEY'
            }]
        
        try:
            # Combine chunks into context (limit to avoid token limits)
            context = "\n\n---QUESTION---\n\n".join(chunks[:20])  # Limit to 20 chunks
            
            prompt = f"""
You are a technical interviewer at {company_name}. Below are coding questions commonly asked at {company_name}:

{context}

Your tasks:
1. Analyze all the questions above
2. Select the BEST question that tests core algorithms and data structures
3. Generate {num_questions} similar questions based on the best one you selected
4. Provide complete Python solutions for each generated question

Format your response as a JSON array where each element has:
- "question": Clear problem statement with example inputs/outputs
- "solution": Complete Python solution with comments explaining the approach

Make sure each question is different but tests similar concepts.
"""
            
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Try to extract JSON from response
            # Look for JSON array pattern
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                questions = json.loads(json_str)
                return questions[:num_questions]
            else:
                # Fallback: parse manually or return first chunk
                logger.warning("Could not parse JSON from Gemini response, using fallback")
                fallback_question = chunks[0] if chunks else "Write a function to solve a coding problem."
                return [{
                    'question': fallback_question,
                    'solution': 'Solution not available. Please try regenerating.'
                }]
                
        except Exception as e:
            logger.error(f"Error generating questions: {str(e)}")
            fallback_question = chunks[0] if chunks else "Write a function to solve a coding problem."
            return [{
                'question': fallback_question,
                'solution': f'Error generating questions: {str(e)}'
            }]
    
    def select_and_generate_system_design_question(self, chunks, company_name):
        """
        Select best system design question from chunks and generate a similar one.
        
        Args:
            chunks (list[str]): List of text chunks from company documents
            company_name (str): Company name for context
            
        Returns:
            dict: Dict with 'question' and 'evaluation_criteria' keys
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                'question': 'Error: Gemini API not configured',
                'evaluation_criteria': 'Please configure GEMINI_API_KEY'
            }
        
        try:
            # Combine chunks into context (limit to avoid token limits)
            context = "\n\n---QUESTION---\n\n".join(chunks[:20])  # Limit to 20 chunks
            
            prompt = f"""
You are a technical interviewer at {company_name}. Below are system design questions commonly asked at {company_name}:

{context}

Your tasks:
1. Analyze all the system design questions above
2. Select the BEST question that tests scalability, architecture, and design thinking
3. Generate 1 similar system design question based on the best one you selected
4. Provide clear evaluation criteria for assessing the answer

Format your response as a JSON object with:
- "question": Clear problem statement with requirements and constraints
- "evaluation_criteria": List of key aspects to evaluate in the answer

Make sure the question is challenging but appropriate for a new grad/entry-level engineer.
"""
            
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Try to extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                question_data = json.loads(json_str)
                return question_data
            else:
                # Fallback: use first chunk
                logger.warning("Could not parse JSON from Gemini response, using fallback")
                fallback_question = chunks[0] if chunks else "Design a scalable system."
                return {
                    'question': fallback_question,
                    'evaluation_criteria': ['Scalability', 'Design clarity', 'Trade-off analysis']
                }
                
        except Exception as e:
            logger.error(f"Error generating system design question: {str(e)}")
            fallback_question = chunks[0] if chunks else "Design a scalable system."
            return {
                'question': fallback_question,
                'evaluation_criteria': ['Scalability', 'Design clarity']
            }
    
    def evaluate_system_design(self, question, user_answer, evaluation_criteria=None):
        """
        Evaluate user's system design answer.
        
        Args:
            question (str): The system design question
            user_answer (str): User's submitted answer
            evaluation_criteria (list): Optional list of criteria to evaluate against
            
        Returns:
            dict: Contains 'is_correct', 'feedback', 'score', 'strengths', 'improvements'
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                'is_correct': False,
                'feedback': 'Gemini API not configured',
                'score': 0,
                'strengths': [],
                'improvements': ['Configure API to enable evaluation']
            }
        
        try:
            criteria_text = ""
            if evaluation_criteria:
                if isinstance(evaluation_criteria, list):
                    criteria_text = "\nEvaluation Criteria:\n" + "\n".join(f"- {c}" for c in evaluation_criteria)
                else:
                    criteria_text = f"\nEvaluation Criteria:\n{evaluation_criteria}"
            
            prompt = f"""
You are an expert system design interviewer evaluating a candidate's answer.

Problem:
{question}
{criteria_text}

Candidate's Answer:
{user_answer}

Please evaluate the candidate's system design answer and provide:

1. **Quality**: Is this a good system design answer? (Yes/No)
2. **Score**: Rate the answer from 0-100 based on:
   - Completeness of the design
   - Consideration of scalability and trade-offs
   - Clear explanation of architecture
   - Handling of edge cases and constraints
3. **Strengths**: List 2-4 positive aspects of the answer
4. **Areas for Improvement**: List 2-4 specific suggestions to improve the design
5. **Detailed Feedback**: Provide 2-3 paragraphs of constructive feedback

Format your response EXACTLY as follows:
QUALITY: [Yes/No]
SCORE: [0-100]

STRENGTHS:
- [Strength 1]
- [Strength 2]

IMPROVEMENTS:
- [Improvement 1]
- [Improvement 2]

FEEDBACK:
[Your detailed feedback here]
"""
            
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Parse response
            is_correct = False
            score = 0
            strengths = []
            improvements = []
            feedback = ""
            
            # Extract quality
            if "QUALITY:" in response_text:
                quality_line = response_text.split("QUALITY:")[1].split("\n")[0].strip().lower()
                is_correct = 'yes' in quality_line
            
            # Extract score
            if "SCORE:" in response_text:
                score_line = response_text.split("SCORE:")[1].split("\n")[0].strip()
                try:
                    score = int(''.join(filter(str.isdigit, score_line)))
                    score = max(0, min(100, score))
                except:
                    score = 50
            
            # Extract strengths
            if "STRENGTHS:" in response_text and "IMPROVEMENTS:" in response_text:
                strengths_text = response_text.split("STRENGTHS:")[1].split("IMPROVEMENTS:")[0].strip()
                strengths = [line.strip('- ').strip() for line in strengths_text.split('\n') if line.strip().startswith('-')]
            
            # Extract improvements
            if "IMPROVEMENTS:" in response_text and "FEEDBACK:" in response_text:
                improvements_text = response_text.split("IMPROVEMENTS:")[1].split("FEEDBACK:")[0].strip()
                improvements = [line.strip('- ').strip() for line in improvements_text.split('\n') if line.strip().startswith('-')]
            
            # Extract feedback
            if "FEEDBACK:" in response_text:
                feedback = response_text.split("FEEDBACK:")[1].strip()
            
            return {
                'is_correct': is_correct,
                'score': score,
                'strengths': strengths,
                'improvements': improvements,
                'feedback': feedback
            }
            
        except Exception as e:
            logger.error(f"Error evaluating system design: {str(e)}")
            return {
                'is_correct': False,
                'feedback': f'Error evaluating system design: {str(e)}',
                'score': 0,
                'strengths': [],
                'improvements': ['Please try again']
            }
    
    def generate_final_analysis(self, session_data):
        """
        Generate comprehensive final analysis based on all completed sections.
        
        Args:
            session_data (dict): Contains all scores and feedback from sections
            
        Returns:
            dict: Contains 'overall_score' and 'analysis' keys
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                'overall_score': 0,
                'analysis': 'Gemini API not configured'
            }
        
        try:
            prompt = f"""
You are a technical recruiter providing final interview feedback for a candidate interviewing at {session_data.get('company', 'a tech company')}.

Here are the results from all interview sections:

**Resume Analysis:**
- Fit Score: {session_data.get('resume_score', 0)}/100
- Analysis: {session_data.get('resume_analysis', 'N/A')}

**Coding Question 1:**
- Score: {session_data.get('coding_q1_score', 0)}/100
- Correctness: {session_data.get('coding_q1_correct', 'N/A')}

**Coding Question 2:**
- Score: {session_data.get('coding_q2_score', 0)}/100
- Correctness: {session_data.get('coding_q2_correct', 'N/A')}

**System Design:**
- Score: {session_data.get('system_design_score', 0)}/100
- Quality: {session_data.get('system_design_quality', 'N/A')}

Based on all the above sections, provide:

1. **Overall Readiness Score**: A single score from 0-100 indicating the candidate's overall readiness for this role
2. **Comprehensive Analysis**: 4-5 paragraphs covering:
   - Overall performance summary across all sections
   - Key strengths demonstrated
   - Critical areas needing improvement
   - Specific recommendations for interview preparation
   - Final assessment of interview readiness

Format your response EXACTLY as follows:
OVERALL_SCORE: [0-100]

ANALYSIS:
[Your comprehensive analysis here]
"""
            
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Parse response
            overall_score = 0
            analysis = ""
            
            # Extract overall score
            if "OVERALL_SCORE:" in response_text:
                score_line = response_text.split("OVERALL_SCORE:")[1].split("\n")[0].strip()
                try:
                    overall_score = int(''.join(filter(str.isdigit, score_line)))
                    overall_score = max(0, min(100, overall_score))
                except:
                    # Calculate average if parsing fails
                    scores = [
                        session_data.get('resume_score', 0),
                        session_data.get('coding_q1_score', 0),
                        session_data.get('coding_q2_score', 0),
                        session_data.get('system_design_score', 0)
                    ]
                    overall_score = sum(scores) // len(scores)
            
            # Extract analysis
            if "ANALYSIS:" in response_text:
                analysis = response_text.split("ANALYSIS:")[1].strip()
            else:
                analysis = response_text
            
            return {
                'overall_score': overall_score,
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Error generating final analysis: {str(e)}")
            # Calculate simple average as fallback
            scores = [
                session_data.get('resume_score', 0),
                session_data.get('coding_q1_score', 0),
                session_data.get('coding_q2_score', 0),
                session_data.get('system_design_score', 0)
            ]
            avg_score = sum(scores) // len(scores) if scores else 0
            
            return {
                'overall_score': avg_score,
                'analysis': f'Error generating analysis: {str(e)}'
            }
    
    def evaluate_code(self, question, reference_solution, user_code, language='python'):
        """
        Evaluate user's code solution against reference solution.
        
        Args:
            question (str): The coding question
            reference_solution (str): The reference solution
            user_code (str): User's submitted code
            language (str): Programming language
            
        Returns:
            dict: Contains 'is_correct', 'feedback', 'score', 'strengths', 'improvements'
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                'is_correct': False,
                'feedback': 'Gemini API not configured',
                'score': 0,
                'strengths': [],
                'improvements': ['Configure API to enable evaluation']
            }
        
        try:
            prompt = f"""
You are an expert technical interviewer evaluating a candidate's coding solution.

Problem:
{question}

Reference Solution:
{reference_solution}

Candidate's Solution ({language}):
{user_code}

Please evaluate the candidate's solution and provide:

1. **Correctness**: Does the solution correctly solve the problem? (Yes/No)
2. **Score**: Rate the solution from 0-100 based on correctness, efficiency, code quality
3. **Strengths**: List 2-3 positive aspects of the solution
4. **Areas for Improvement**: List 2-3 specific suggestions to improve the solution
5. **Detailed Feedback**: Provide 2-3 paragraphs of constructive feedback

Format your response EXACTLY as follows:
CORRECTNESS: [Yes/No]
SCORE: [0-100]

STRENGTHS:
- [Strength 1]
- [Strength 2]

IMPROVEMENTS:
- [Improvement 1]
- [Improvement 2]

FEEDBACK:
[Your detailed feedback here]
"""
            
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Parse response
            is_correct = False
            score = 0
            strengths = []
            improvements = []
            feedback = ""
            
            # Extract correctness
            if "CORRECTNESS:" in response_text:
                correctness_line = response_text.split("CORRECTNESS:")[1].split("\n")[0].strip().lower()
                is_correct = 'yes' in correctness_line
            
            # Extract score
            if "SCORE:" in response_text:
                score_line = response_text.split("SCORE:")[1].split("\n")[0].strip()
                try:
                    score = int(''.join(filter(str.isdigit, score_line)))
                    score = max(0, min(100, score))
                except:
                    score = 50
            
            # Extract strengths
            if "STRENGTHS:" in response_text and "IMPROVEMENTS:" in response_text:
                strengths_text = response_text.split("STRENGTHS:")[1].split("IMPROVEMENTS:")[0].strip()
                strengths = [line.strip('- ').strip() for line in strengths_text.split('\n') if line.strip().startswith('-')]
            
            # Extract improvements
            if "IMPROVEMENTS:" in response_text and "FEEDBACK:" in response_text:
                improvements_text = response_text.split("IMPROVEMENTS:")[1].split("FEEDBACK:")[0].strip()
                improvements = [line.strip('- ').strip() for line in improvements_text.split('\n') if line.strip().startswith('-')]
            
            # Extract feedback
            if "FEEDBACK:" in response_text:
                feedback = response_text.split("FEEDBACK:")[1].strip()
            
            return {
                'is_correct': is_correct,
                'score': score,
                'strengths': strengths,
                'improvements': improvements,
                'feedback': feedback
            }
            
        except Exception as e:
            logger.error(f"Error evaluating code: {str(e)}")
            return {
                'is_correct': False,
                'feedback': f'Error evaluating code: {str(e)}',
                'score': 0,
                'strengths': [],
                'improvements': ['Please try again']
            }

