[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [DateTimeOffset] $StartDateTime,

    [Parameter(Mandatory)]
    [DateTimeOffset] $EndDateTime
)

Set-StrictMode -Version Latest

function Select-M365MessageCenterNewUnread {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [AllowEmptyCollection()]
        [object[]] $Message,

        [Parameter(Mandatory)]
        [DateTimeOffset] $StartDateTime,

        [Parameter(Mandatory)]
        [DateTimeOffset] $EndDateTime
    )

    if ($EndDateTime -le $StartDateTime) {
        throw 'EndDateTime must be later than StartDateTime.'
    }

    foreach ($item in $Message) {
        if ($null -eq $item.ViewPoint) {
            throw ('Message "{0}" has no viewPoint. Connect with delegated ServiceMessage.Read.All permission; app-only authentication cannot determine unread status.' -f $item.Id)
        }
    }

    Write-Verbose ('Retrieved messages: {0}' -f $Message.Count)

    $inPeriod = @(
        $Message | Where-Object {
            $lastModified = [DateTimeOffset] $_.LastModifiedDateTime
            $lastModified -ge $StartDateTime -and $lastModified -lt $EndDateTime
        }
    )
    Write-Verbose ('Messages in requested period: {0}' -f $inPeriod.Count)

    $unread = @(
        $inPeriod | Where-Object {
            $null -ne $_.ViewPoint.IsRead -and $_.ViewPoint.IsRead -eq $false
        }
    )
    Write-Verbose ('Unread messages in requested period: {0}' -f $unread.Count)

    $withoutUpdatedTag = @(
        $unread | Where-Object {
            @($_.Tags) -notcontains 'Updated message'
        }
    )
    Write-Verbose ('Unread messages excluding Updated message tags: {0}' -f $withoutUpdatedTag.Count)

    $newUnread = @(
        $withoutUpdatedTag | Where-Object {
            $_.Title -notmatch '^\(Updated\)'
        }
    )
    Write-Verbose ('New unread messages returned: {0}' -f $newUnread.Count)

    $newUnread |
        ForEach-Object {
            [PSCustomObject]@{
                Id                       = $_.Id
                Title                    = $_.Title
                LastModifiedDateTime     = [DateTimeOffset] $_.LastModifiedDateTime
                Services                 = @($_.Services)
                Category                 = $_.Category
                Severity                 = $_.Severity
                ActionRequiredByDateTime = if ($null -eq $_.ActionRequiredByDateTime) {
                    $null
                }
                else {
                    [DateTimeOffset] $_.ActionRequiredByDateTime
                }
            }
        } |
        Sort-Object -Property LastModifiedDateTime -Descending
}

function Get-M365MessageCenterNewUnread {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [DateTimeOffset] $StartDateTime,

        [Parameter(Mandatory)]
        [DateTimeOffset] $EndDateTime
    )

    if ($EndDateTime -le $StartDateTime) {
        throw 'EndDateTime must be later than StartDateTime.'
    }

    if ($null -eq (Get-Command -Name Get-MgServiceAnnouncementMessage -ErrorAction SilentlyContinue)) {
        throw 'Get-MgServiceAnnouncementMessage is unavailable. Install Microsoft.Graph.Devices.ServiceAnnouncement.'
    }

    if ($null -eq (Get-Command -Name Get-MgContext -ErrorAction SilentlyContinue)) {
        throw 'Get-MgContext is unavailable. Install Microsoft.Graph.Authentication.'
    }

    $context = Get-MgContext
    if ($null -eq $context) {
        throw "No Microsoft Graph session exists. Run Connect-MgGraph -Scopes 'ServiceMessage.Read.All' -ContextScope Process."
    }

    if ($context.AuthType -eq 'AppOnly') {
        throw 'App-only authentication cannot determine unread status. Connect with delegated ServiceMessage.Read.All permission.'
    }

    if (@($context.Scopes) -notcontains 'ServiceMessage.Read.All') {
        throw "The Microsoft Graph session lacks ServiceMessage.Read.All. Reconnect with Connect-MgGraph -Scopes 'ServiceMessage.Read.All' -ContextScope Process."
    }

    $properties = @(
        'id'
        'title'
        'lastModifiedDateTime'
        'services'
        'category'
        'severity'
        'actionRequiredByDateTime'
        'tags'
        'viewPoint'
    )

    $messages = @(Get-MgServiceAnnouncementMessage -All -Property $properties)
    Select-M365MessageCenterNewUnread -Message $messages -StartDateTime $StartDateTime -EndDateTime $EndDateTime
}

if ($MyInvocation.InvocationName -ne '.') {
    Get-M365MessageCenterNewUnread -StartDateTime $StartDateTime -EndDateTime $EndDateTime
}
