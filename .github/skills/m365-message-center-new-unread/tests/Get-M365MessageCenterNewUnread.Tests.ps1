$scriptPath = Join-Path $PSScriptRoot '..\scripts\Get-M365MessageCenterNewUnread.ps1'
. $scriptPath -StartDateTime '2026-06-01T00:00:00Z' -EndDateTime '2026-06-08T00:00:00Z'

function New-TestMessage {
    param(
        [string] $Id,
        [string] $Title = 'New feature',
        [string] $LastModifiedDateTime = '2026-06-03T00:00:00Z',
        [AllowNull()]
        [object] $IsRead = $false,
        [AllowNull()]
        [object] $ViewPoint = ([PSCustomObject]@{ IsRead = $IsRead }),
        [string[]] $Tags = @()
    )

    [PSCustomObject]@{
        Id                       = $Id
        Title                    = $Title
        LastModifiedDateTime     = $LastModifiedDateTime
        Services                 = @('Microsoft 365')
        Category                 = 'planForChange'
        Severity                 = 'normal'
        ActionRequiredByDateTime = $null
        Tags                     = $Tags
        ViewPoint                = $ViewPoint
    }
}

Describe 'Select-M365MessageCenterNewUnread' {
    $start = [DateTimeOffset] '2026-06-01T00:00:00Z'
    $end = [DateTimeOffset] '2026-06-08T00:00:00Z'

    It 'keeps only new unread messages and sorts newest first' {
        $messages = @(
            (New-TestMessage -Id 'MC1' -LastModifiedDateTime '2026-06-01T00:00:00Z')
            (New-TestMessage -Id 'MC2' -LastModifiedDateTime '2026-06-07T23:59:59Z')
            (New-TestMessage -Id 'READ' -IsRead $true)
            (New-TestMessage -Id 'TAGGED' -Tags @('Updated message'))
            (New-TestMessage -Id 'TITLE' -Title '(Updated) Existing feature')
            (New-TestMessage -Id 'BEFORE' -LastModifiedDateTime '2026-05-31T23:59:59Z')
            (New-TestMessage -Id 'END' -LastModifiedDateTime '2026-06-08T00:00:00Z')
        )

        $result = @(Select-M365MessageCenterNewUnread -Message $messages -StartDateTime $start -EndDateTime $end)

        $result.Count | Should Be 2
        $result[0].Id | Should Be 'MC2'
        $result[1].Id | Should Be 'MC1'
    }

    It 'excludes a message when unread status is not explicit' {
        $message = New-TestMessage -Id 'UNKNOWN' -IsRead $null

        $result = @(Select-M365MessageCenterNewUnread -Message @($message) -StartDateTime $start -EndDateTime $end)

        $result.Count | Should Be 0
    }

    It 'rejects an invalid period' {
        $thrown = $false
        try {
            Select-M365MessageCenterNewUnread -Message @() -StartDateTime $end -EndDateTime $start
        }
        catch {
            $thrown = $true
        }

        $thrown | Should Be $true
    }

    It 'rejects a null viewpoint' {
        $message = New-TestMessage -Id 'APPONLY' -ViewPoint $null

        $thrown = $false
        try {
            Select-M365MessageCenterNewUnread -Message @($message) -StartDateTime $start -EndDateTime $end
        }
        catch {
            $thrown = $true
        }

        $thrown | Should Be $true
    }
}

Describe 'Get-M365MessageCenterNewUnread' {
    function Get-MgServiceAnnouncementMessage {
        param(
            [switch] $All,
            [string[]] $Property
        )
    }
    function Get-MgContext {}

    Mock Get-Command {
        [PSCustomObject]@{ Name = $Name }
    }
    Mock Get-MgContext {
        [PSCustomObject]@{
            AuthType = 'Delegated'
            Scopes   = @('ServiceMessage.Read.All')
        }
    }
    $script:graphCalledWithAll = $false
    Mock Get-MgServiceAnnouncementMessage {
        $script:graphCalledWithAll = [bool] $All
        @(
            (New-TestMessage -Id 'NEW')
            (New-TestMessage -Id 'OLD-UPDATE' -Tags @('Updated message'))
        )
    }

    It 'retrieves all pages and filters the Graph response' {
        $result = @(Get-M365MessageCenterNewUnread `
            -StartDateTime '2026-06-01T00:00:00Z' `
            -EndDateTime '2026-06-08T00:00:00Z')

        $result.Count | Should Be 1
        $result[0].Id | Should Be 'NEW'
        $script:graphCalledWithAll | Should Be $true
    }
}
