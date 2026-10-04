import chromadb
from sentence_transformers import SentenceTransformer
from ollama import chat


model = SentenceTransformer("all-MiniLM-L6-V2")

chunks = [
    "Agile uses short iterations called sprints.",
    "Plants perform photosynthesis.",
    "Sprint planning happens before a sprint."
]

embeddings = model.encode(chunks)
client = chromadb.Client()
collection = client.create_collection("documents")

collection.add(
    ids = ["chunk_1", "chunk_2", "chunk_3"],
    embeddings = embeddings,
    documents = chunks
)

question = "What is the capital of France?"

question_embedding = model.encode([question])

results = collection.query(
    query_embeddings= question_embedding,
    n_results = 2
    )

context = "\n".join(results["documents"][0])

response = chat(
    model = "qwen2.5:1.5b",
    messages=[
        {
            "role" : "user",
            "content" : f"""
            You are a document question-answering assistant.

            Use ONLY the information in the CONTEXT below.

            If the answer cannot be found in the CONTEXT, respond exactly:
            "I don't know based on the provided document."

            Do not use your own knowledge.
            
            context : {context}
            
            Question : {question}
            """
            
        }
    ]
)

print(response.message.content)