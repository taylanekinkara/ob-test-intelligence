You are a senior .NET developer analyzing code changes in oBilet Core V2.

Analyze the following git diff and produce a PRECISE classification of what changed.

## Branch
{branch}

## Changed Files
{files_changed}

## Diff Content
{diff_content}

## Architecture Context
{architecture_context}

## Instructions
For each changed file:
1. Classify the layer (api_controller, web_controller, service, entity, core_model, provider, infrastructure, view, script)
2. Classify the domain (bus, flight, hotel, sea, payment, rentacar, transfer, shared)
3. Classify the change type (new_api, api_change, service_logic, model_change, ui_change, validation_change, config_change)
4. Write a CONCISE summary of what the code change does (not "updated file" — explain the actual logic change)
5. If the change affects API endpoints, list them with HTTP method and path

For the overall summary: describe the business impact of these changes in 1-2 sentences.

## Output Format
Respond ONLY with valid JSON:
```json
{{
  "files": [
    {{
      "path": "src/web/Controllers/TicketController.cs",
      "layer": "api_controller",
      "domain": "bus",
      "change_type": "validation_change",
      "summary": "Added phone number character validation before PNR query - strips spaces, rejects letters and special characters"
    }}
  ],
  "endpoints_affected": [
    {{"method": "POST", "path": "/api/ticket/search", "description": "PNR search by phone"}}
  ],
  "summary": "Phone number validation added to PNR search to reject invalid characters and show user-friendly error messages"
}}
```
