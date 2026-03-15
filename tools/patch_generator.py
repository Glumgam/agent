def generate_patch_prompt(error_summary) -> list:
    prompts = []
    if not error_summary:
        return prompts

    for item in error_summary:
        err_type = item.get("type", "")
        if err_type == "network_error":
            prompts.append(
                {
                    "file": "tools/web_tools.py",
                    "prompt": (
                        "Add retry with exponential backoff for urlopen/DNS failures. "
                        "Limit retries to 2 and log when retries occur."
                    ),
                }
            )
        elif err_type == "timeout":
            prompts.append(
                {
                    "file": "tools/web_tools.py",
                    "prompt": (
                        "Add retry for timeout errors and consider increasing timeout "
                        "to 15s with a max of 2 retries."
                    ),
                }
            )
        elif err_type == "robots_blocked":
            prompts.append(
                {
                    "file": "tools/web_tools.py",
                    "prompt": (
                        "When robots.txt blocks a URL, switch to an alternate source "
                        "or skip the URL with a clear log entry."
                    ),
                }
            )
        elif err_type == "permission_error":
            prompts.append(
                {
                    "file": "tools/system_tools.py",
                    "prompt": (
                        "Improve permission error handling by adding clearer messages "
                        "and safe fallbacks where possible."
                    ),
                }
            )
        else:
            prompts.append(
                {
                    "file": "executor.py",
                    "prompt": (
                        "Improve error handling for unknown failures with contextual "
                        "logging and structured errors."
                    ),
                }
            )

    return prompts
