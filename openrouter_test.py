import os
import requests


# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY is not set.\n"
        "Set it in your terminal before running this program."
    )

URL = "https://openrouter.ai/api/v1/chat/completions"

# OpenRouter automatically selects an available free model
MODEL = "openrouter/free"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


# ============================================================
# API CALL
# ============================================================

def call_model(messages):

    response = requests.post(
        URL,
        headers=HEADERS,
        json={
            "model": MODEL,
            "messages": messages,

            # Enable reasoning when the selected model supports it
            "reasoning": {
                "enabled": True
            }
        },
        timeout=120
    )

    print("\n" + "=" * 60)
    print("HTTP STATUS:", response.status_code)
    print("=" * 60)

    # --------------------------------------------------------
    # ERROR HANDLING
    # --------------------------------------------------------

    if response.status_code != 200:

        print("API ERROR:")
        print(response.text)

        if response.status_code == 401:
            print("\n❌ Authentication error.")
            print("Check your OPENROUTER_API_KEY.")

        elif response.status_code == 402:
            print("\n❌ Payment/provider error.")
            print("The selected provider may require credits.")

        elif response.status_code == 429:
            print("\n⚠️ Rate limited.")
            print("Wait and try again later.")

        return None

    # --------------------------------------------------------
    # PARSE RESPONSE
    # --------------------------------------------------------

    data = response.json()

    # --------------------------------------------------------
    # SHOW ACTUAL MODEL
    # --------------------------------------------------------

    actual_model = data.get("model")

    print("🤖 MODEL USED:")
    print(actual_model)

    # --------------------------------------------------------
    # CHECK CHOICES
    # --------------------------------------------------------

    if "choices" not in data:

        print("\n❌ Unexpected API response:")
        print(data)

        return None

    message = data["choices"][0]["message"]

    # --------------------------------------------------------
    # SHOW RESPONSE
    # --------------------------------------------------------

    print("\nASSISTANT:")
    print(message.get("content"))

    # --------------------------------------------------------
    # SHOW REASONING INFORMATION
    # --------------------------------------------------------

    reasoning_details = message.get("reasoning_details")

    print("\nREASONING_DETAILS:")

    if reasoning_details:
        print("✅ Present")
        print("Number of reasoning items:", len(reasoning_details))
    else:
        print("ℹ️ Not returned by this model")

    return message


# ============================================================
# FIRST CALL
# ============================================================

print("\n")
print("#" * 60)
print("# FIRST CALL")
print("#" * 60)

messages = [
    {
        "role": "user",
        "content": (
            "How many r's are in the word "
            "'strawberry'? Explain briefly."
        )
    }
]


first_message = call_model(messages)


if first_message is None:
    print("\n❌ First call failed.")
    raise SystemExit


# ============================================================
# SAVE THE ASSISTANT MESSAGE
# ============================================================

reasoning_details = first_message.get("reasoning_details")

messages.append({
    "role": "assistant",
    "content": first_message.get("content"),
    "reasoning_details": reasoning_details
})


# ============================================================
# SECOND USER MESSAGE
# ============================================================

messages.append({
    "role": "user",
    "content": (
        "Are you sure? Think carefully and check "
        "your answer again."
    )
})


# ============================================================
# SECOND CALL
# ============================================================

print("\n")
print("#" * 60)
print("# SECOND CALL")
print("#" * 60)

second_message = call_model(messages)


if second_message is None:
    print("\n❌ Second call failed.")
    raise SystemExit


# ============================================================
# FINISHED
# ============================================================

print("\n")
print("#" * 60)
print("# TEST COMPLETE")
print("#" * 60)