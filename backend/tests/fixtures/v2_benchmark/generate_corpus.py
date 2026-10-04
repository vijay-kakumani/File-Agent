"""
V2 Benchmark Controlled Corpus Generator.
Creates a realistic, deterministic test corpus with nested folders, multiple file formats (PDF, DOCX, TXT, MD),
duplicate filenames, and verifiable ground-truth facts.
"""

from pathlib import Path
import pymupdf  # PyMuPDF
import docx      # python-docx

CORPUS_ROOT = Path(__file__).resolve().parent / "corpus"


def create_pdf(filepath: Path, title: str, paragraphs: list[str]):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)  # Standard Letter
    
    # Title
    p_title = pymupdf.Point(50, 60)
    page.insert_text(p_title, title, fontsize=16, fontname="helv", color=(0, 0, 0))
    
    y = 90
    for p in paragraphs:
        # Wrap or split long lines
        rect = pymupdf.Rect(50, y, 562, y + 60)
        page.insert_textbox(rect, p, fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        y += 70
        if y > 720:
            page = doc.new_page(width=612, height=792)
            y = 60
            
    doc.save(str(filepath))
    doc.close()


def create_docx(filepath: Path, title: str, paragraphs: list[str]):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc = docx.Document()
    doc.add_heading(title, level=1)
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(str(filepath))


def create_txt(filepath: Path, content: str):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def create_md(filepath: Path, content: str):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def generate_benchmark_corpus(corpus_dir: Path = CORPUS_ROOT):
    """
    Generates the entire controlled benchmark corpus under corpus_dir.
    """
    c_sim = corpus_dir / "C_drive_sim"
    d_sim = corpus_dir / "D_drive_sim"

    # 1. C_drive_sim/Downloads/Vijay_Resume.pdf
    create_pdf(
        c_sim / "Downloads" / "Vijay_Resume.pdf",
        "Vijay Kakumani - Software Engineer Resume",
        [
            "Candidate: Vijay Kakumani. Email: vijay@example.com. Location: Hyderabad, India.",
            "Summary: Software Engineer specializing in backend development, distributed systems, and modern web architectures.",
            "Education: Bachelor of Technology in Computer Science, State University, GPA 3.8/4.0.",
            "Technical Skills: Programming Languages: Python, JavaScript, SQL. Frameworks & Libraries: React, FastAPI, Node.js. Databases: PostgreSQL, SQLite. Version Control & Tools: Git, GitHub, Linux.",
            "Key Projects: CampusConnect - Collaborative academic platform for university students built with FastAPI, React, and PostgreSQL. Implemented real-time messaging, peer reviews, and secure file sharing.",
            "Key Projects: Local AI Document Agent - Desktop agent for natural language document discovery and local vector embeddings.",
            "Professional Experience: TechCorp Solutions - Software Engineering Intern (June 2025 to August 2025). Developed REST APIs using FastAPI, optimized PostgreSQL queries, and implemented caching."
        ]
    )

    # 2. C_drive_sim/Downloads/Resume.pdf (Duplicate name, different content)
    create_pdf(
        c_sim / "Downloads" / "Resume.pdf",
        "General Candidate Resume - Frontend Focus",
        [
            "Candidate: Alex Johnson. Role: Frontend UI/UX Developer.",
            "Skills: HTML5, CSS3, Tailwind CSS, JavaScript, React, Figma, Responsive Web Design.",
            "Experience: Freelance Web Designer building user interfaces and wireframes for consumer web portals."
        ]
    )

    # 3. D_drive_sim/College/Resume.pdf (Duplicate name in D drive)
    create_pdf(
        d_sim / "College" / "Resume.pdf",
        "Academic CV - Graduate Research Track",
        [
            "Candidate: Rohan Sharma. Research Focus: Data Mining and Graph Algorithms.",
            "Education: Bachelor of Science in Information Technology.",
            "Academic Publications: Survey on Community Detection Algorithms in Social Networks."
        ]
    )

    # 3b. C_drive_sim/Downloads/Nikhil_CS_Resume.pdf (For fuzzy filename testing)
    create_pdf(
        c_sim / "Downloads" / "Nikhil_CS_Resume.pdf",
        "Nikhil Chandra - Computer Science Resume",
        [
            "Candidate: Nikhil Chandra. Title: Computer Science Graduate.",
            "Technical Skills: C++, Java, Python, Algorithms, Data Structures.",
            "Projects: Compiler design and distributed hash tables."
        ]
    )

    # 4. C_drive_sim/Downloads/CampusConnect_Report.pdf
    create_pdf(
        c_sim / "Downloads" / "CampusConnect_Report.pdf",
        "CampusConnect Project Comprehensive Report",
        [
            "Executive Summary: CampusConnect is a web application designed for university students to share course notes, collaborate on academic assignments, and organize study groups.",
            "Architecture: Built with a decoupled client-server architecture. The frontend is built in React with TypeScript. The backend is built using Python FastAPI with asynchronous request handlers.",
            "Database: PostgreSQL serves as the primary relational database, storing student profiles, course groups, and message threads.",
            "Key Features: 1. Course-Specific Collaboration Channels. 2. Real-Time Peer-to-Peer Messaging. 3. Secure Academic File Uploads (PDF and DOCX). 4. Peer Rating and Content Moderation. 5. Role-Based Access Control.",
            "Security: End-to-end token validation using JWT with hashed passwords and sanitized inputs."
        ]
    )

    # 5. D_drive_sim/College/Projects/CampusConnect/Project_Report.docx
    create_docx(
        d_sim / "College" / "Projects" / "CampusConnect" / "Project_Report.docx",
        "CampusConnect Technical Project Documentation",
        [
            "Project Title: CampusConnect Academic Collaboration Suite.",
            "Technologies: Python 3.12, FastAPI, React 19, PostgreSQL 16, Vite, Tailwind CSS.",
            "Database Design: Relational schema comprising Users, Courses, Channels, Posts, Comments, and ResourceAttachments tables with foreign key constraints.",
            "API Specification: REST endpoints for user authentication, channel management, and file uploads.",
            "Deployment: Packaged as Docker containers orchestrated via Docker Compose."
        ]
    )

    # 6. C_drive_sim/Documents/College/4th_Year/Internship/Internship_Report.pdf (Document A - 8 weeks)
    create_pdf(
        c_sim / "Documents" / "College" / "4th_Year" / "Internship" / "Internship_Report.pdf",
        "TechCorp Solutions Final Internship Report",
        [
            "Author: Vijay Kakumani. Program: 4th Year Computer Science. Academic Year: 2025-2026.",
            "Supervisor: Dr. Aris Thorne, Engineering Director at TechCorp Solutions.",
            "Duration: The internship duration was 8 weeks, commencing on June 2, 2025, and concluding on July 25, 2025.",
            "Assigned Project: CampusConnect Integration and High-Performance Document Search Engine.",
            "Technologies Used: Python, FastAPI, React, PostgreSQL.",
            "Measurable Achievements: Reduced document search latency by 40% and improved indexing throughput.",
            "Conclusion: Successfully completed all milestones within the 8 weeks internship period."
        ]
    )

    # 7. D_drive_sim/College/4th_Year/Internship/Internship_Report_External.pdf (Document B - Conflicting 12 weeks)
    create_pdf(
        d_sim / "College" / "4th_Year" / "Internship" / "Internship_Report_External.pdf",
        "Global Systems Inc External Internship Report",
        [
            "Author: Alex Mercer. Program: Computer Systems Engineering.",
            "Company: Global Systems Inc.",
            "Duration: The internship duration was 12 weeks, spanning from May 15, 2024, to August 10, 2024.",
            "Assigned Project: Legacy Enterprise Portal Migration.",
            "Technologies Used: Java, Spring Boot, Angular, Oracle DB.",
            "Outcome: Migrated 50 legacy JSP enterprise forms to Angular components."
        ]
    )

    # 8. D_drive_sim/College/Agile/Agile_Methodologies.docx
    create_docx(
        d_sim / "College" / "Agile" / "Agile_Methodologies.docx",
        "Agile Methodologies and Scrum Framework Guide",
        [
            "Overview: Agile is an iterative approach to project management and software development that helps teams deliver value faster and with greater quality.",
            "Scrum Sprints: Scrum is structured around fixed-length iterations called sprints. In our team, sprint duration is 2 weeks.",
            "Core Scrum Roles: 1. Product Owner (defines product vision, prioritizes product backlog). 2. Scrum Master (coaches team, facilitates events, removes impediments). 3. Development Team (cross-functional engineers delivering the sprint increment).",
            "Scrum Ceremonies: 1. Sprint Planning (agile planning at sprint start). 2. Daily Standup (15-minute daily synchronization meeting). 3. Sprint Review (demo of working software to stakeholders). 4. Sprint Retrospective (team reflection and process improvement).",
            "Artifacts: Product Backlog, Sprint Backlog, and the Shippable Product Increment."
        ]
    )

    # 9. D_drive_sim/Projects/Python/Machine_Learning_Notes.txt
    create_txt(
        d_sim / "Projects" / "Python" / "Machine_Learning_Notes.txt",
        """Machine Learning Fundamentals and Study Notes

1. Supervised Learning:
Algorithms trained on labeled input-output pairs. Common examples include Linear Regression, Logistic Regression, Decision Trees, and Random Forests.

2. Linear Regression:
Models the linear relationship between independent input variable X and dependent output variable Y.
Mathematical formulation: y = w * x + b, where w represents the weight and b represents the bias.

3. Gradient Descent:
An iterative optimization algorithm used to minimize the objective loss function.
Weight update rule: w = w - alpha * grad, where alpha is the learning rate and grad is the gradient of the loss function with respect to weight w.

4. Neural Networks:
Layers of interconnected artificial neurons computing non-linear transformations using activation functions such as ReLU, Sigmoid, and Tanh.
Trained using backpropagation and stochastic gradient descent.

5. Machine Learning Frameworks:
Primary libraries: PyTorch, Scikit-Learn, NumPy, and Pandas.
"""
    )

    # 10. D_drive_sim/Projects/Python/Python_Backend_Guide.md
    create_md(
        d_sim / "Projects" / "Python" / "Python_Backend_Guide.md",
        """# Python Backend Architecture Best Practices

## Asynchronous Services with FastAPI
FastAPI leverages Python asynchronous capabilities (async/await) and ASGI web servers such as Uvicorn to achieve high concurrency.

## Dependency Injection
Use FastAPI `Depends()` for database sessions, authentication context, and configuration injection.

## Data Validation with Pydantic
Define strict Pydantic BaseModel schemas for all API request payloads and response models.
"""
    )

    # 11. D_drive_sim/Projects/Python/System_Architecture_Spec.md
    create_md(
        d_sim / "Projects" / "Python" / "System_Architecture_Spec.md",
        """# System Architecture Specification

## Overview
High-level architectural blueprint for local desktop AI systems, describing inter-process communication, local SQLite caches, and vector indexing.

## Components
1. Tauri v2 Desktop Shell (Rust + WebView2)
2. FastAPI Localhost Microservice (Python 3.12)
3. SQLite FTS5 Full-Text Database
4. ChromaDB Vector Database
5. Sentence-Transformers Local Embedding Pipeline
"""
    )

    # 12. C_drive_sim/Downloads/Q3_Budget_Summary.pdf
    create_pdf(
        c_sim / "Downloads" / "Q3_Budget_Summary.pdf",
        "Quarter 3 Departmental Budget and Financial Summary",
        [
            "Financial Allocation: Total allocated budget for Q3 is $45,000.",
            "Breakdown: Infrastructure & Cloud Hosting: $20,000. Marketing & Outreach: $15,000. Software Tool Licenses: $10,000.",
            "Notes: Expenditure approved by Departmental Finance Committee.",
            "Disclaimer: Does not disclose executive compensation, private salary data, or overall corporate net revenue."
        ]
    )

    # 13. C_drive_sim/Documents/Certifications/AWS_Cloud_Practitioner_Certificate.pdf
    create_pdf(
        c_sim / "Documents" / "Certifications" / "AWS_Cloud_Practitioner_Certificate.pdf",
        "AWS Certified Cloud Practitioner Certificate of Completion",
        [
            "Recipient: Vijay Kakumani.",
            "Credential Identifier: AWS-CCP-987654321.",
            "Issue Date: January 15, 2025.",
            "Description: Validates foundational knowledge of AWS cloud platform concepts, security, architecture, pricing models, and client support."
        ]
    )

    # 14. C_drive_sim/Desktop/Meeting_Notes.txt
    create_txt(
        c_sim / "Desktop" / "Meeting_Notes.txt",
        """Weekly Engineering Sync Notes
Date: September 14, 2026

1. Sprint Deliverables:
   - Finalized user authentication endpoints.
   - Closed 8 bug tickets related to file uploads.
2. Next Steps:
   - Begin benchmark evaluation harness.
   - Schedule release demo for next Thursday.
"""
    )

    # 15. D_drive_sim/Personal/Tax_Receipt_2025.txt
    create_txt(
        d_sim / "Personal" / "Tax_Receipt_2025.txt",
        """Annual Tax Filing Acknowledgement 2025
Filing Status: Accepted
Assessment Year: 2025-2026
Submission ID: TX-2025-88410294
"""
    )


if __name__ == "__main__":
    generate_benchmark_corpus()
    print(f"Corpus generated successfully in {CORPUS_ROOT}")
