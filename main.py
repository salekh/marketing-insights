import os
from google import genai
from google.cloud import aiplatform

# For Vertex AI (GCP)
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "sa-learning-1")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")

def init_vertex():
    # google-cloud-aiplatform initialization
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    print(f"Vertex AI initialized for project {PROJECT_ID} in {LOCATION}")

def demo_genai_sdk():
    """Example using the new google-genai SDK with Vertex AI."""
    # The google-genai SDK automatically uses Application Default Credentials
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    print(f"google-genai client initialized for Vertex AI (Project: {PROJECT_ID}, Location: {LOCATION})")
    
    # Example usage (commented out to avoid execution without auth)
    # try:
    #     response = client.models.generate_content(model="gemini-2.0-flash", contents="Hello from sa-learning-1!")
    #     print(f"Response: {response.text}")
    # except Exception as e:
    #     print(f"Note: Content generation failed (check auth/quotas): {e}")

if __name__ == "__main__":
    init_vertex()
    demo_genai_sdk()
