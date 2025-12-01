"""
Gemini AI service for resume analysis and interview preparation.
"""

import io
import json
import logging

import google.generativeai as genai
from django.conf import settings
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


class GeminiAnalyzer:
    """Service class for Gemini AI-powered resume analysis and interview generation"""

    def __init__(self):
        """Initialize Gemini AI with API key"""
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
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
            if hasattr(resume_file, "read"):
                pdf_content = resume_file.read()
                resume_file.seek(0)  # Reset file pointer
            else:
                with open(resume_file, "rb") as f:
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
            dict: Contains (
                'fit_score' (int 0-100), 'analysis' (str), 'suggestions' (str)
            )
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                "fit_score": 0,
                "analysis": (
                    "Gemini API key is not configured. Please add GEMINI_API_KEY to "
                    "your environment variables."
                ),
                "suggestions": (
                    "Configure the API key to enable AI-powered resume analysis."
                ),
            }

        try:
            # Create the prompt for Gemini
            prompt = f"""
{(f"You are an expert technical recruiter analyzing a candidate's resume for a position at {company_name}.")}

Job Description:
{job_description}

Candidate's Resume:
{resume_text}

Please provide a comprehensive analysis with the following:

1. **Fit Score**: Rate how well this resume matches the job description on a scale of \
0-100. Just provide the number.

2. **Detailed Analysis**: Provide a thorough analysis (3-4 paragraphs) covering:
   - Key strengths and relevant experiences
   - How well the candidate's skills align with job requirements
   - Notable achievements and qualifications
   - Areas where the candidate excels for this role

3. **Improvement Suggestions**: Provide 5-7 specific, actionable suggestions to \
improve the resume for this position. Format as a bulleted list. Each \
suggestion should be concrete and implementable.

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
                    fit_score = int("".join(filter(str.isdigit, score_line)))
                    fit_score = max(0, min(100, fit_score))  # Ensure 0-100 range
                except ValueError:
                    fit_score = 50  # Default if parsing fails

            # Extract analysis
            if "ANALYSIS:" in response_text and "SUGGESTIONS:" in response_text:
                analysis = (
                    response_text.split("ANALYSIS:")[1].split("SUGGESTIONS:")[0].strip()
                )
            elif "ANALYSIS:" in response_text:
                analysis = response_text.split("ANALYSIS:")[1].strip()

            # Extract suggestions
            if "SUGGESTIONS:" in response_text:
                suggestions = response_text.split("SUGGESTIONS:")[1].strip()

            # Fallback if parsing fails
            if not analysis:
                analysis = response_text

            return {
                "fit_score": fit_score,
                "analysis": analysis,
                "suggestions": suggestions,
            }

        except Exception as e:
            return {
                "fit_score": 0,
                "analysis": f"An error occurred while analyzing the resume: {str(e)}",
                "suggestions": (
                    "Please try again later or check your API configuration."
                ),
            }

    def select_and_generate_questions(
        self, document_text, company_name, num_questions=2
    ):
        """
        Select best question from document and generate similar coding questions.
        Gemini does the intelligent selection and generation.

        Args:
            document_text (str): Full text from one company document
            company_name (str): Company name for context
            num_questions (int): Number of questions to generate

        Returns:
            list[dict]: List of dicts with 'question' and 'solution' keys
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return [
                {
                    "question": "Error: Gemini API not configured",
                    "solution": "Please configure GEMINI_API_KEY",
                }
            ]

        if not document_text:
            logger.warning("Empty document text provided")
            return [
                {
                    "question": "Write a function to solve a coding problem.",
                    "solution": "No company-specific questions available.",
                }
            ]

        try:
            prompt = f"""
You are a technical interviewer at {company_name}. Below is a document containing coding question \
titles/names commonly asked at {company_name}:

{document_text}

Your tasks:
1. **Parse and extract ALL individual question titles** from the document above (e.g., "Rotate Image", \
"Minimum Window Substring", "Course Schedule", etc.)
2. **Randomly select {num_questions} DIFFERENT question titles** from the extracted list
3. **For EACH selected title, create a complete LeetCode-style problem** including:
   
   a) **Problem Title**: Use the exact title from the document
   
   b) **Problem Description**: Write a clear, detailed problem statement explaining what needs to be solved
   
   c) **Examples**: Provide 2-3 example test cases with:
      - Input (clearly formatted)
      - Output (expected result)
      - Explanation (optional, if helpful)
   
   d) **Constraints**: List constraints such as:
      - Input size/range limits (e.g., "1 <= n <= 10^4")
      - Value ranges (e.g., "-10^9 <= nums[i] <= 10^9")
      - Expected time/space complexity (e.g., "Try to solve in O(n) time")
   
   e) **Edge Cases**: Mention important edge cases to consider (e.g., empty input, single element, \
all same values, etc.)
   
   f) **Solution**: Provide a complete, optimal Python solution with:
      - Detailed comments explaining the approach
      - Time and space complexity analysis in comments
      - Clean, readable code following best practices

4. **IMPORTANT**: Base your questions ONLY on the exact titles from the document. Do NOT invent new \
question titles. If the document says "Rotate Image", create the standard LeetCode "Rotate Image" problem.

Format your response as a JSON array where each element has:
- "question": The complete problem (title + description + examples + constraints + edge cases, all \
formatted as one text block)
- "solution": Complete optimal Python solution with detailed comments

Example format for the "question" field:
\"\"\"
**Problem: [Title from document]**

[Problem description]

**Example 1:**
Input: [input]
Output: [output]
Explanation: [optional]

**Example 2:**
Input: [input]
Output: [output]

**Constraints:**
- [constraint 1]
- [constraint 2]

**Edge Cases to Consider:**
- [edge case 1]
- [edge case 2]
\"\"\"

Ensure each of the {num_questions} questions is based on a DIFFERENT title from the document.
"""

            response = self.model.generate_content(prompt)
            response_text = response.text

            # Try to extract JSON from response
            # Look for JSON array pattern
            start_idx = response_text.find("[")
            end_idx = response_text.rfind("]") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                questions = json.loads(json_str)
                logger.info(
                    f"Successfully generated {len(questions)} coding questions for {company_name}"
                )
                return questions[:num_questions]
            else:
                # Fallback: parse manually or return excerpt from document
                logger.warning(
                    f"Could not parse JSON from Gemini response for {company_name}. "
                    f"Response text preview: {response_text[:200]}"
                )
                # Try to extract question titles from the original document for debugging
                lines = document_text.split("\n")
                potential_titles = [
                    line.strip()
                    for line in lines[:20]
                    if line.strip() and len(line.strip()) > 5
                ]
                logger.info(
                    f"Found potential question titles in document: {potential_titles[:10]}"
                )

                fallback_question = (
                    f"**Problem: Coding Challenge**\n\n{document_text[:500]}\n\n"
                    f"**Note**: Question generation failed. Please ensure the document "
                    f"contains clear question titles."
                    if document_text
                    else "Write a function to solve a coding problem."
                )
                return [
                    {
                        "question": fallback_question,
                        "solution": (
                            "Solution not available. Please regenerate or check document format."
                        ),
                    }
                ]

        except json.JSONDecodeError as e:
            logger.error(
                f"JSON parsing error for {company_name}: {str(e)}. "
                f"Raw response preview: {response_text[:300] if 'response_text' in locals() else 'N/A'}"
            )
            # Extract question titles from document for debugging
            lines = document_text.split("\n")
            potential_titles = [
                line.strip()
                for line in lines[:20]
                if line.strip() and len(line.strip()) > 5
            ]
            logger.info(f"Document contains potential titles: {potential_titles[:10]}")

            fallback_question = (
                f"**Problem: Coding Challenge**\n\n{document_text[:500]}\n\n"
                f"**Note**: Question parsing failed. Document preview shown above."
                if document_text
                else "Write a function to solve a coding problem."
            )
            return [
                {
                    "question": fallback_question,
                    "solution": f"Error parsing questions: {str(e)}. Please check document format.",
                }
            ]
        except Exception as e:
            logger.error(f"Error generating questions for {company_name}: {str(e)}")
            # Try to show what's in the document for debugging
            lines = document_text.split("\n") if document_text else []
            potential_titles = [
                line.strip()
                for line in lines[:20]
                if line.strip() and len(line.strip()) > 5
            ]
            if potential_titles:
                logger.info(
                    f"Document content preview (potential titles): {potential_titles[:10]}"
                )

            fallback_question = (
                f"**Problem: Coding Challenge**\n\n{document_text[:500]}"
                if document_text
                else "Write a function to solve a coding problem."
            )
            return [
                {
                    "question": fallback_question,
                    "solution": f"Error generating questions: {str(e)}",
                }
            ]

    def select_and_generate_system_design_question(self, document_text, company_name):
        """
        Select one actual system design question from document and elaborate it
        as it would appear in a real interview.

        Args:
            document_text (str): Full text from one company document
            company_name (str): Company name for context

        Returns:
            dict: Dict with 'question' and 'evaluation_criteria' keys
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                "question": "Error: Gemini API not configured",
                "evaluation_criteria": ["Please configure GEMINI_API_KEY"],
            }

        if not document_text:
            logger.warning("Empty document text provided")
            return {
                "question": "Design a scalable system.",
                "evaluation_criteria": ["Scalability", "Design clarity"],
            }

        try:
            prompt = f"""
You are a technical interviewer at {company_name}. Below are system design questions \
commonly asked at {company_name}:

{document_text}

Your tasks:
1. Analyze all the system design questions above
2. Select ONE actual question from the list that best tests scalability, architecture, and design thinking
3. Elaborate the selected question as it would appear in a real interview by:
   - Expanding it with clear requirements and functional specifications
   - Adding realistic constraints (scale, latency, availability, etc.)
   - Including context about expected usage patterns
   - Making it interview-ready with specific details
4. Keep the core question intact - do NOT generate a similar or different question
5. Provide clear evaluation criteria for assessing the answer

Format your response as a JSON object with:
- "question": The elaborated version of the selected question formatted in Markdown with:
  * A clear title/heading (## Title)
  * Well-structured sections with headers (### Section Name)
  * Bullet points for requirements and specifications (- item)
  * Bold text for emphasis (**text**)
  * Proper spacing and organization
  * Structure it like: Title, Prompt/Description, Requirements (with Functional and Non-functional subsections), Context/Usage Patterns, Interview Guidance
- "evaluation_criteria": List of evaluation criteria, where each criterion is a string formatted as:
  * "**Criterion Title:** Detailed description/question about what to evaluate"
  * Each criterion should be comprehensive and specific
  * Examples:
    - "**High-Level Architecture:** Does the candidate propose a sensible overall system architecture, identifying core components (e.g., API Gateway, Storage Service, Metadata Service) and their interactions?"
    - "**Scalability & Performance:** How does the design address millions of users, petabytes of data, and high request rates? Consider strategies like sharding, partitioning, caching, CDN, and load balancing."
    - "**Data Management:** What storage technologies are chosen? How is data sharded, replicated, and geo-distributed for durability and availability?"

The question should be well-organized and easy to read, formatted with proper Markdown syntax including headers, bullet points, and bold text for emphasis.

Make sure the elaborated question is challenging but appropriate for a new grad/entry-level engineer.
"""

            response = self.model.generate_content(prompt)
            response_text = response.text

            # Try to extract JSON from response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                question_data = json.loads(json_str)
                return question_data
            else:
                # Fallback: use excerpt from document
                logger.warning(
                    "Could not parse JSON from Gemini response, using fallback"
                )
                fallback_question = (
                    document_text[:500]
                    if document_text
                    else "Design a scalable system."
                )
                return {
                    "question": fallback_question,
                    "evaluation_criteria": [
                        "Scalability",
                        "Design clarity",
                        "Trade-off analysis",
                    ],
                }

        except Exception as e:
            logger.error(f"Error generating system design question: {str(e)}")
            fallback_question = (
                document_text[:500] if document_text else "Design a scalable system."
            )
            return {
                "question": fallback_question,
                "evaluation_criteria": ["Scalability", "Design clarity"],
            }

    def evaluate_system_design(
        self, question, user_answer, evaluation_criteria=None, design_image=None
    ):
        """
        Evaluate user's system design answer.

        Args:
            question (str): The system design question
            user_answer (str): User's submitted answer
            evaluation_criteria (list): Optional list of criteria to evaluate against
            design_image: Optional image file (Django ImageField) containing architecture diagram

        Returns:
            dict: Contains 'is_correct', 'feedback', 'score', 'strengths', 'improvements'
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                "is_correct": False,
                "feedback": "Gemini API not configured",
                "score": 0,
                "strengths": [],
                "improvements": ["Configure API to enable evaluation"],
            }

        try:
            criteria_text = ""
            if evaluation_criteria:
                if isinstance(evaluation_criteria, list):
                    criteria_text = "\nEvaluation Criteria:\n" + "\n".join(
                        f"- {c}" for c in evaluation_criteria
                    )
                else:
                    criteria_text = f"\nEvaluation Criteria:\n{evaluation_criteria}"

            # Prepare content parts (text + optional image)
            content_parts = []

            prompt_text = f"""
You are an expert system design interviewer evaluating a candidate's answer.

Problem:
{question}
{criteria_text}

Candidate's Answer:
{user_answer}
"""

            # Add image if provided
            if design_image:
                import PIL.Image

                # Read the image file
                # Handle Django ImageField (has .path attribute)
                if hasattr(design_image, "path"):
                    # It's a saved ImageField instance
                    image = PIL.Image.open(design_image.path)
                elif hasattr(design_image, "read"):
                    # It's a file-like object (uploaded file)
                    image_bytes = design_image.read()
                    design_image.seek(0)  # Reset file pointer
                    image = PIL.Image.open(io.BytesIO(image_bytes))
                else:
                    # Fallback: try to open as path string
                    image = PIL.Image.open(design_image)

                content_parts.append(image)
                prompt_text += "\n\nThe candidate has also provided an architecture diagram/image. Please analyze it along with their text answer and consider:\n- How well the diagram illustrates their design\n- Clarity and completeness of the visual representation\n- Alignment between the diagram and written description\n"

            prompt_text += """
Please evaluate the candidate's system design answer and provide:

1. **Quality**: Is this a good system design answer? (Yes/No)
2. **Score**: Rate the answer from 0-100 based on:
   - Completeness of the design
   - Consideration of scalability and trade-offs
   - Clear explanation of architecture
   - Handling of edge cases and constraints
   - Quality of visual diagram (if provided)
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

            content_parts.append(prompt_text)

            # Generate content with or without image
            response = self.model.generate_content(content_parts)
            response_text = response.text

            # Parse response
            is_correct = False
            score = 0
            strengths = []
            improvements = []
            feedback = ""

            # Extract quality
            if "QUALITY:" in response_text:
                quality_line = (
                    response_text.split("QUALITY:")[1].split("\n")[0].strip().lower()
                )
                is_correct = "yes" in quality_line

            # Extract score
            if "SCORE:" in response_text:
                score_line = response_text.split("SCORE:")[1].split("\n")[0].strip()
                try:
                    score = int("".join(filter(str.isdigit, score_line)))
                    score = max(0, min(100, score))
                except ValueError:
                    score = 50

            # Extract strengths
            if "STRENGTHS:" in response_text and "IMPROVEMENTS:" in response_text:
                strengths_text = (
                    response_text.split("STRENGTHS:")[1]
                    .split("IMPROVEMENTS:")[0]
                    .strip()
                )
                strengths = [
                    line.strip("- ").strip()
                    for line in strengths_text.split("\n")
                    if line.strip().startswith("-")
                ]

            # Extract improvements
            if "IMPROVEMENTS:" in response_text and "FEEDBACK:" in response_text:
                improvements_text = (
                    response_text.split("IMPROVEMENTS:")[1]
                    .split("FEEDBACK:")[0]
                    .strip()
                )
                improvements = [
                    line.strip("- ").strip()
                    for line in improvements_text.split("\n")
                    if line.strip().startswith("-")
                ]

            # Extract feedback
            if "FEEDBACK:" in response_text:
                feedback = response_text.split("FEEDBACK:")[1].strip()

            return {
                "is_correct": is_correct,
                "score": score,
                "strengths": strengths,
                "improvements": improvements,
                "feedback": feedback,
            }

        except Exception as e:
            logger.error(f"Error evaluating system design: {str(e)}")
            return {
                "is_correct": False,
                "feedback": f"Error evaluating system design: {str(e)}",
                "score": 0,
                "strengths": [],
                "improvements": ["Please try again"],
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
            return {"overall_score": 0, "analysis": "Gemini API not configured"}

        try:
            prompt = f"""
You are a technical recruiter providing final interview feedback for a candidate interviewing at {session_data.get("company", "a tech company")}.

Here are the results from all interview sections:

**Resume Analysis:**
- Fit Score: {session_data.get("resume_score", 0)}/100
- Analysis: {session_data.get("resume_analysis", "N/A")}

**Coding Question 1:**
- Score: {session_data.get("coding_q1_score", 0)}/100
- Correctness: {session_data.get("coding_q1_correct", "N/A")}

**Coding Question 2:**
- Score: {session_data.get("coding_q2_score", 0)}/100
- Correctness: {session_data.get("coding_q2_correct", "N/A")}

**System Design:**
- Score: {session_data.get("system_design_score", 0)}/100
- Quality: {session_data.get("system_design_quality", "N/A")}

**Behavioral + Resume Interview:**
- Summary: {session_data.get("behavioral_resume_summary", "Not completed")}

Based on all the above sections, provide:

1. **Overall Readiness Score**: A single score from 0-100 indicating the candidate's overall readiness for this role (consider all sections including technical skills and behavioral performance)
2. **Comprehensive Analysis**: 4-5 paragraphs covering:
   - Overall performance summary across all sections (technical and behavioral)
   - Key strengths demonstrated in coding, system design, and behavioral communication
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
                score_line = (
                    response_text.split("OVERALL_SCORE:")[1].split("\n")[0].strip()
                )
                try:
                    overall_score = int("".join(filter(str.isdigit, score_line)))
                    overall_score = max(0, min(100, overall_score))
                except ValueError:
                    # Calculate average if parsing fails
                    scores = [
                        session_data.get("resume_score", 0),
                        session_data.get("coding_q1_score", 0),
                        session_data.get("coding_q2_score", 0),
                        session_data.get("system_design_score", 0),
                    ]
                    overall_score = sum(scores) // len(scores)

            # Extract analysis
            if "ANALYSIS:" in response_text:
                analysis = response_text.split("ANALYSIS:")[1].strip()
            else:
                analysis = response_text

            return {"overall_score": overall_score, "analysis": analysis}

        except Exception as e:
            logger.error(f"Error generating final analysis: {str(e)}")
            # Calculate simple average as fallback
            scores = [
                session_data.get("resume_score", 0),
                session_data.get("coding_q1_score", 0),
                session_data.get("coding_q2_score", 0),
                session_data.get("system_design_score", 0),
            ]
            avg_score = sum(scores) // len(scores) if scores else 0

            return {
                "overall_score": avg_score,
                "analysis": f"Error generating analysis: {str(e)}",
            }

    def generate_final_analysis_pm(self, session_data):
        """
        Generate comprehensive final analysis for PM candidates based on all completed sections.

        Args:
            session_data (dict): Contains all scores and feedback from PM sections

        Returns:
            dict: Contains 'overall_score' and 'analysis' keys
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {"overall_score": 0, "analysis": "Gemini API not configured"}

        try:
            prompt = f"""
You are a product management recruiter providing final interview feedback for a PM candidate interviewing at {session_data.get("company", "a tech company")}.

Here are the results from all interview sections:

**Resume Analysis:**
- Fit Score: {session_data.get("resume_score", 0)}/100
- Analysis: {session_data.get("resume_analysis", "N/A")}

**Product Sense:**
- Score: {session_data.get("product_sense_score", 0)}/100
- Quality: {session_data.get("product_sense_quality", "N/A")}

**Analytical + Strategy:**
- Score: {session_data.get("analytical_strategy_score", 0)}/100
- Quality: {session_data.get("analytical_strategy_quality", "N/A")}

**Behavioral + Resume Interview:**
- Summary: {session_data.get("behavioral_resume_summary", "Not completed")}

Based on all the above sections, provide:

1. **Overall Readiness Score**: A single score from 0-100 indicating the candidate's overall readiness for this PM role
2. **Comprehensive Analysis**: 4-5 paragraphs covering:
   - Overall performance summary across all sections
   - Key PM competencies demonstrated (product thinking, analytical skills, leadership, etc.)
   - Critical areas needing improvement
   - Specific recommendations for PM interview preparation
   - Final assessment of PM interview readiness

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
                score_line = (
                    response_text.split("OVERALL_SCORE:")[1].split("\n")[0].strip()
                )
                try:
                    overall_score = int("".join(filter(str.isdigit, score_line)))
                    overall_score = max(0, min(100, overall_score))
                except ValueError:
                    # Calculate average if parsing fails
                    scores = [
                        session_data.get("resume_score", 0),
                        session_data.get("product_sense_score", 0),
                        session_data.get("analytical_strategy_score", 0),
                    ]
                    overall_score = sum(scores) // len(scores)

            # Extract analysis
            if "ANALYSIS:" in response_text:
                analysis = response_text.split("ANALYSIS:")[1].strip()
            else:
                analysis = response_text

            return {"overall_score": overall_score, "analysis": analysis}

        except Exception as e:
            logger.error(f"Error generating PM final analysis: {str(e)}")
            # Calculate simple average as fallback
            scores = [
                session_data.get("resume_score", 0),
                session_data.get("product_sense_score", 0),
                session_data.get("analytical_strategy_score", 0),
            ]
            avg_score = sum(scores) // len(scores) if scores else 0

            return {
                "overall_score": avg_score,
                "analysis": f"Error generating analysis: {str(e)}",
            }

    def evaluate_code(self, question, reference_solution, user_code, language="python"):
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
                "is_correct": False,
                "feedback": "Gemini API not configured",
                "score": 0,
                "strengths": [],
                "improvements": ["Configure API to enable evaluation"],
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
                correctness_line = (
                    response_text.split("CORRECTNESS:")[1]
                    .split("\n")[0]
                    .strip()
                    .lower()
                )
                is_correct = "yes" in correctness_line

            # Extract score
            if "SCORE:" in response_text:
                score_line = response_text.split("SCORE:")[1].split("\n")[0].strip()
                try:
                    score = int("".join(filter(str.isdigit, score_line)))
                    score = max(0, min(100, score))
                except ValueError:
                    score = 50

            # Extract strengths
            if "STRENGTHS:" in response_text and "IMPROVEMENTS:" in response_text:
                strengths_text = (
                    response_text.split("STRENGTHS:")[1]
                    .split("IMPROVEMENTS:")[0]
                    .strip()
                )
                strengths = [
                    line.strip("- ").strip()
                    for line in strengths_text.split("\n")
                    if line.strip().startswith("-")
                ]

            # Extract improvements
            if "IMPROVEMENTS:" in response_text and "FEEDBACK:" in response_text:
                improvements_text = (
                    response_text.split("IMPROVEMENTS:")[1]
                    .split("FEEDBACK:")[0]
                    .strip()
                )
                improvements = [
                    line.strip("- ").strip()
                    for line in improvements_text.split("\n")
                    if line.strip().startswith("-")
                ]

            # Extract feedback
            if "FEEDBACK:" in response_text:
                feedback = response_text.split("FEEDBACK:")[1].strip()

            return {
                "is_correct": is_correct,
                "score": score,
                "strengths": strengths,
                "improvements": improvements,
                "feedback": feedback,
            }

        except Exception as e:
            logger.error(f"Error evaluating code: {str(e)}")
            return {
                "is_correct": False,
                "feedback": f"Error evaluating code: {str(e)}",
                "score": 0,
                "strengths": [],
                "improvements": ["Please try again"],
            }

    def select_and_generate_product_sense_case(self, document_text, company_name):
        """
        Select one actual product sense question from document and elaborate it
        as it would appear in a real interview.

        Args:
            document_text (str): Full text from one company document
            company_name (str): Company name for context

        Returns:
            dict: Dict with 'case' and 'evaluation_criteria' keys
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                "case": "Error: Gemini API not configured",
                "evaluation_criteria": ["Please configure GEMINI_API_KEY"],
            }

        if not document_text:
            logger.warning("Empty document text provided")
            return {
                "case": (
                    "Design a new feature to improve user engagement for our product."
                ),
                "evaluation_criteria": [
                    "User-centricity",
                    "Problem framing",
                    "Metrics",
                ],
            }

        try:
            prompt = f"""
You are a product management interviewer at {company_name}. Below are product sense questions \
commonly asked at {company_name}:

{document_text}

Your tasks:
1. Parse and extract ALL individual product sense questions from the document above (e.g., "Design an app for an amusement park", \
"How would you improve Google Chrome?", "Design a product for travel", etc.)
2. Randomly select ONE actual question from the extracted list
3. Elaborate the selected question as it would appear in a real interview by:
   - Expanding it with clear context and problem statement
   - Adding realistic constraints and considerations
   - Including what aspects you're looking for in the answer
   - Making it interview-ready with specific details and guidance
4. Keep the core question intact - do NOT generate a similar or different question
5. Provide clear evaluation criteria for assessing the answer

Format your response as a JSON object with:
- "case": The elaborated version of the selected question formatted in Markdown with:
  * A clear title/heading (## Title)
  * Well-structured sections with headers (### Section Name)
  * Bullet points for requirements and considerations (- item)
  * Bold text for emphasis (**text**)
  * Proper spacing and organization
  * Structure it like: Title, Problem Statement/Context, What We're Looking For, Key Considerations, Interview Guidance
- "evaluation_criteria": List of evaluation criteria, where each criterion is a string formatted as:
  * "**Criterion Title:** Detailed description/question about what to evaluate"
  * Each criterion should be comprehensive and specific
  * Examples:
    - "**User-Centricity:** Does the candidate demonstrate deep understanding of user needs, pain points, and motivations? Do they identify the right user segments?"
    - "**Problem Framing:** How well does the candidate define and scope the problem? Do they ask clarifying questions and identify root causes?"
    - "**Metrics & Success Criteria:** What metrics does the candidate propose to measure success? Are they relevant, measurable, and aligned with business goals?"
    - "**Prioritization & Trade-offs:** Does the candidate demonstrate ability to prioritize features/solutions? Do they discuss trade-offs and make data-driven decisions?"

The case should be well-organized and easy to read, formatted with proper Markdown syntax including headers, bullet points, and bold text for emphasis.

Make sure the elaborated case is challenging but appropriate for a product manager role.
"""

            response = self.model.generate_content(prompt)
            response_text = response.text

            # Try to extract JSON from response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                case_data = json.loads(json_str)
                return case_data
            else:
                # Fallback: use excerpt from document
                logger.warning(
                    "Could not parse JSON from Gemini response, using fallback"
                )
                fallback_case = (
                    document_text[:500]
                    if document_text
                    else "Design a new feature to improve user engagement for our product."
                )
                return {
                    "case": fallback_case,
                    "evaluation_criteria": [
                        "User-centricity",
                        "Problem framing",
                        "Metrics definition",
                        "Prioritization",
                        "Trade-off analysis",
                    ],
                }

        except Exception as e:
            logger.error(f"Error generating product sense case: {str(e)}")
            fallback_case = (
                document_text[:500]
                if document_text
                else "Design a new feature to improve user engagement for our product."
            )
            return {
                "case": fallback_case,
                "evaluation_criteria": [
                    "User-centricity",
                    "Problem framing",
                    "Metrics",
                ],
            }

    def evaluate_product_sense(self, case, user_answer, evaluation_criteria=None):
        """
        Evaluate user's product sense answer.

        Args:
            case (str): The product sense case
            user_answer (str): User's submitted answer
            evaluation_criteria (list): Optional list of criteria to evaluate against

        Returns:
            dict: Contains 'is_good', 'feedback', 'score', 'strengths', 'improvements'
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                "is_good": False,
                "feedback": "Gemini API not configured",
                "score": 0,
                "strengths": [],
                "improvements": ["Configure API to enable evaluation"],
            }

        try:
            criteria_text = ""
            if evaluation_criteria:
                if isinstance(evaluation_criteria, list):
                    criteria_text = "\nEvaluation Criteria:\n" + "\n".join(
                        f"- {c}" for c in evaluation_criteria
                    )
                else:
                    criteria_text = f"\nEvaluation Criteria:\n{evaluation_criteria}"

            prompt = f"""
You are an expert product management interviewer evaluating a candidate's product sense answer.

Product Sense Case:
{case}
{criteria_text}

Candidate's Answer:
{user_answer}

Please evaluate the candidate's product sense answer and provide:

1. **Quality**: Is this a good product sense answer? (Yes/No)
2. **Score**: Rate the answer from 0-100 based on:
   - User-centricity and empathy
   - Problem framing and clarity
   - Metrics and success criteria
   - Prioritization and trade-off analysis
   - Strategic thinking
3. **Strengths**: List 2-4 positive aspects of the answer
4. **Areas for Improvement**: List 2-4 specific suggestions to improve the answer
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
            is_good = False
            score = 0
            strengths = []
            improvements = []
            feedback = ""

            # Extract quality
            if "QUALITY:" in response_text:
                quality_line = (
                    response_text.split("QUALITY:")[1].split("\n")[0].strip().lower()
                )
                is_good = "yes" in quality_line

            # Extract score
            if "SCORE:" in response_text:
                score_line = response_text.split("SCORE:")[1].split("\n")[0].strip()
                try:
                    score = int("".join(filter(str.isdigit, score_line)))
                    score = max(0, min(100, score))
                except ValueError:
                    score = 50

            # Extract strengths
            if "STRENGTHS:" in response_text and "IMPROVEMENTS:" in response_text:
                strengths_text = (
                    response_text.split("STRENGTHS:")[1]
                    .split("IMPROVEMENTS:")[0]
                    .strip()
                )
                strengths = [
                    line.strip("- ").strip()
                    for line in strengths_text.split("\n")
                    if line.strip().startswith("-")
                ]

            # Extract improvements
            if "IMPROVEMENTS:" in response_text and "FEEDBACK:" in response_text:
                improvements_text = (
                    response_text.split("IMPROVEMENTS:")[1]
                    .split("FEEDBACK:")[0]
                    .strip()
                )
                improvements = [
                    line.strip("- ").strip()
                    for line in improvements_text.split("\n")
                    if line.strip().startswith("-")
                ]

            # Extract feedback
            if "FEEDBACK:" in response_text:
                feedback = response_text.split("FEEDBACK:")[1].strip()

            return {
                "is_good": is_good,
                "score": score,
                "strengths": strengths,
                "improvements": improvements,
                "feedback": feedback,
            }

        except Exception as e:
            logger.error(f"Error evaluating product sense: {str(e)}")
            return {
                "is_good": False,
                "feedback": f"Error evaluating product sense: {str(e)}",
                "score": 0,
                "strengths": [],
                "improvements": ["Please try again"],
            }

    def select_and_generate_analytical_strategy_question(
        self, document_text, company_name
    ):
        """
        Select one actual analytical/strategy question from document and elaborate it
        as it would appear in a real interview.

        Args:
            document_text (str): Full text from one company document
            company_name (str): Company name for context

        Returns:
            dict: Dict with 'question' and 'evaluation_criteria' keys
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                "question": "Error: Gemini API not configured",
                "evaluation_criteria": ["Please configure GEMINI_API_KEY"],
            }

        if not document_text:
            logger.warning("Empty document text provided")
            return {
                "question": (
                    "Design an experiment to test a new feature's impact on user retention."
                ),
                "evaluation_criteria": [
                    "Hypothesis clarity",
                    "Metrics",
                    "Analytical rigor",
                ],
            }

        try:
            prompt = f"""
You are a product management interviewer at {company_name}. Below are analytical and strategy questions \
commonly asked at {company_name}:

{document_text}

Your tasks:
1. Parse and extract ALL individual analytical/strategy questions from the document above (e.g., "How would you improve Google Chrome?", \
"Your product's DAU/MAU ratio has been declining. Design an experiment to identify the root cause", \
"Estimate the market size for X", etc.)
2. Randomly select ONE actual question from the extracted list
3. Elaborate the selected question as it would appear in a real interview by:
   - Expanding it with clear context and problem statement
   - Adding realistic constraints and data considerations
   - Including what aspects you're looking for in the answer
   - Making it interview-ready with specific details and guidance
4. Keep the core question intact - do NOT generate a similar or different question
5. Provide clear evaluation criteria for assessing the answer

Format your response as a JSON object with:
- "question": The elaborated version of the selected question formatted in Markdown with:
  * A clear title/heading (## Title)
  * Well-structured sections with headers (### Section Name)
  * Bullet points for requirements and considerations (- item)
  * Bold text for emphasis (**text**)
  * Proper spacing and organization
  * Structure it like: Title, Problem Statement/Context, What We're Looking For, Key Considerations, Interview Guidance
- "evaluation_criteria": List of evaluation criteria, where each criterion is a string formatted as:
  * "**Criterion Title:** Detailed description/question about what to evaluate"
  * Each criterion should be comprehensive and specific
  * Examples:
    - "**Hypothesis Clarity:** Does the candidate formulate a clear, testable hypothesis? Is it specific, measurable, and aligned with the problem?"
    - "**Metrics & Measurement:** What metrics does the candidate propose? Are they relevant, measurable, and tied to business outcomes? Do they consider leading vs lagging indicators?"
    - "**Analytical Rigor:** How does the candidate approach data analysis? Do they consider statistical significance, sample sizes, and potential biases?"
    - "**Decision Framework:** Does the candidate provide a clear framework for making decisions based on the analysis? Do they consider trade-offs and risks?"
    - "**Strategic Thinking:** Does the candidate think beyond the immediate problem? Do they consider long-term implications and strategic alignment?"

The question should be well-organized and easy to read, formatted with proper Markdown syntax including headers, bullet points, and bold text for emphasis.

Make sure the elaborated question is challenging but appropriate for a product manager role.
"""

            response = self.model.generate_content(prompt)
            response_text = response.text

            # Try to extract JSON from response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                question_data = json.loads(json_str)
                return question_data
            else:
                # Fallback: use excerpt from document
                logger.warning(
                    "Could not parse JSON from Gemini response, using fallback"
                )
                fallback_question = (
                    document_text[:500]
                    if document_text
                    else "Design an experiment to test a new feature's impact on user retention."
                )
                return {
                    "question": fallback_question,
                    "evaluation_criteria": [
                        "Hypothesis clarity",
                        "Metrics definition",
                        "Analytical rigor",
                        "Decision quality",
                    ],
                }

        except Exception as e:
            logger.error(f"Error generating analytical/strategy question: {str(e)}")
            fallback_question = (
                document_text[:500]
                if document_text
                else "Design an experiment to test a new feature's impact on user retention."
            )
            return {
                "question": fallback_question,
                "evaluation_criteria": [
                    "Hypothesis clarity",
                    "Metrics",
                    "Analytical rigor",
                ],
            }

    def evaluate_analytical_strategy(
        self, question, user_answer, evaluation_criteria=None
    ):
        """
        Evaluate user's analytical/strategy answer.

        Args:
            question (str): The analytical/strategy question
            user_answer (str): User's submitted answer
            evaluation_criteria (list): Optional list of criteria to evaluate against

        Returns:
            dict: Contains 'is_good', 'feedback', 'score', 'strengths', 'improvements'
        """
        if not self.model or not settings.GEMINI_API_KEY:
            return {
                "is_good": False,
                "feedback": "Gemini API not configured",
                "score": 0,
                "strengths": [],
                "improvements": ["Configure API to enable evaluation"],
            }

        try:
            criteria_text = ""
            if evaluation_criteria:
                if isinstance(evaluation_criteria, list):
                    criteria_text = "\nEvaluation Criteria:\n" + "\n".join(
                        f"- {c}" for c in evaluation_criteria
                    )
                else:
                    criteria_text = f"\nEvaluation Criteria:\n{evaluation_criteria}"

            prompt = f"""
You are an expert product management interviewer evaluating a candidate's analytical/strategy answer.

Question:
{question}
{criteria_text}

Candidate's Answer:
{user_answer}

Please evaluate the candidate's analytical/strategy answer and provide:

1. **Quality**: Is this a good analytical/strategy answer? (Yes/No)
2. **Score**: Rate the answer from 0-100 based on:
   - Hypothesis clarity and framing
   - Metrics definition and selection
   - Analytical rigor and data-driven thinking
   - Decision quality and trade-offs
   - Strategic planning
3. **Strengths**: List 2-4 positive aspects of the answer
4. **Areas for Improvement**: List 2-4 specific suggestions to improve the answer
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
            is_good = False
            score = 0
            strengths = []
            improvements = []
            feedback = ""

            # Extract quality
            if "QUALITY:" in response_text:
                quality_line = (
                    response_text.split("QUALITY:")[1].split("\n")[0].strip().lower()
                )
                is_good = "yes" in quality_line

            # Extract score
            if "SCORE:" in response_text:
                score_line = response_text.split("SCORE:")[1].split("\n")[0].strip()
                try:
                    score = int("".join(filter(str.isdigit, score_line)))
                    score = max(0, min(100, score))
                except ValueError:
                    score = 50

            # Extract strengths
            if "STRENGTHS:" in response_text and "IMPROVEMENTS:" in response_text:
                strengths_text = (
                    response_text.split("STRENGTHS:")[1]
                    .split("IMPROVEMENTS:")[0]
                    .strip()
                )
                strengths = [
                    line.strip("- ").strip()
                    for line in strengths_text.split("\n")
                    if line.strip().startswith("-")
                ]

            # Extract improvements
            if "IMPROVEMENTS:" in response_text and "FEEDBACK:" in response_text:
                improvements_text = (
                    response_text.split("IMPROVEMENTS:")[1]
                    .split("FEEDBACK:")[0]
                    .strip()
                )
                improvements = [
                    line.strip("- ").strip()
                    for line in improvements_text.split("\n")
                    if line.strip().startswith("-")
                ]

            # Extract feedback
            if "FEEDBACK:" in response_text:
                feedback = response_text.split("FEEDBACK:")[1].strip()

            return {
                "is_good": is_good,
                "score": score,
                "strengths": strengths,
                "improvements": improvements,
                "feedback": feedback,
            }

        except Exception as e:
            logger.error(f"Error evaluating analytical/strategy: {str(e)}")
            return {
                "is_good": False,
                "feedback": f"Error evaluating analytical/strategy: {str(e)}",
                "score": 0,
                "strengths": [],
                "improvements": ["Please try again"],
            }
