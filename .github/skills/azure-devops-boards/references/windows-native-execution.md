# Windows-Native Azure DevOps Execution

Use this reference whenever Azure Boards work is executed from Windows, especially on a non-English Windows installation.

## Required shell selection

1. Use Azure DevOps MCP tools when available.
2. Otherwise run PowerShell 7 (pwsh) and prefer Invoke-RestMethod.
3. Use the native az boards command from PowerShell only when REST is impractical.

Never use MSYS2, Git Bash, WSL, bash, or sh for Azure DevOps work on Windows. Do not use MSYS_NO_PATHCONV as a workaround; that variable addresses path conversion in a prohibited shell and does not make the shell an approved execution path.

## UTF-8 REST writes

Keep the organization URL, project, and credential in environment variables. In the PowerShell example below, `ADO_TOKEN` must be an Entra ID access token because it is sent as a Bearer token. A PAT is not a Bearer token; use an `Authorization: Basic` header with the PAT instead, following the authentication guidance in the foundation skill. Never print credentials.

PowerShell example:

    $orgUrl = $env:ADO_ORG_URL.TrimEnd('/')
    $project = [Uri]::EscapeDataString($env:ADO_PROJECT)
    $typeName = [Uri]::EscapeDataString($env:ADO_WORK_ITEM_TYPE)
    $title = $env:ADO_WORK_ITEM_TITLE
    $description = $env:ADO_WORK_ITEM_DESCRIPTION

    $patch = @(
        @{ op = 'add'; path = '/fields/System.Title'; value = $title },
        @{ op = 'add'; path = '/fields/System.Description'; value = $description }
    )
    $json = $patch | ConvertTo-Json -Depth 10 -Compress
    $body = [Text.Encoding]::UTF8.GetBytes($json)
    $headers = @{ Authorization = "Bearer $env:ADO_TOKEN" }
    $workItemsSegment = '$' + $typeName
    $uri = "$orgUrl/$project/_apis/wit/workitems/$workItemsSegment?api-version=7.1"

    $created = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json-patch+json; charset=utf-8' -Body $body
    $created.id

Use the same UTF-8 byte conversion for JSON Patch updates and relation links. Read the created item back with Invoke-RestMethod; PowerShell returns the response as Unicode text without relying on the console code page.

## Native az boards fallback

Use az boards directly from PowerShell and retrieve only an ASCII ID when possible:

    $createdId = az boards work-item create --type $env:ADO_WORK_ITEM_TYPE --title $env:ADO_WORK_ITEM_TITLE --description $env:ADO_WORK_ITEM_DESCRIPTION --query id -o tsv

Verify fields with Invoke-RestMethod rather than trusting captured human-readable az output. Azure CLI's MSI launcher uses Python isolated mode, which ignores PYTHONIOENCODING; redirected output can therefore use the Windows ANSI code page. chcp 65001 changes the console code page and does not repair redirected output. Neither behavior means that the server received corrupted data.

If az emits an encoding warning, preserve the original title and description, read the Work Item through REST, and compare the returned fields. Never translate content to English as an encoding workaround.

## Linux/macOS comparison

The following pattern is for Linux/macOS shells only. It must not be copied into a Windows MSYS2 or Git Bash session.

    base_uri="$ADO_ORG_URL/$ADO_PROJECT"
    json="$PATCH_JSON"
    curl --fail-with-body -sS -X POST \
      -H "Authorization: Bearer $ADO_TOKEN" \
      -H 'Content-Type: application/json-patch+json; charset=utf-8' \
      --data-binary "$json" \
      "$base_uri/_apis/wit/workitems/\$$ADO_WORK_ITEM_TYPE?api-version=7.1"

When a Windows session cannot provide PowerShell 7, stop and request that the user run the operation from a native PowerShell environment. Do not silently switch to MSYS2.
