import time

def generate_summary(incident_id):
    # Retrieve incident
    # Retrieve connected alert and metrics
    # Use LLM or template to generate summary
    return f"Incident {incident_id} summary: Device down due to network issue."

def run_agent():
    print("Starting Reporter Agent...")
    while True:
        # Check for Resolved incidents without summary
        time.sleep(60)

if __name__ == "__main__":
    run_agent()
