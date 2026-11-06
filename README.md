# Veronos Studio mockup factory

Builds a homepage concept for each new contact in the Veronos Master Contacts sheet, with no AI and no paid services, and publishes it at `preview.veronosstudio.com/<business>/`.

Each preview is labelled "Concept preview by Veronos Studio, not the official website" and is hidden from search engines.

- Runs nightly at about 3:37 AM Edmonton (after the lead finder), or on demand: Actions > Build mockups > Run workflow.
- Writes each business's status ("mockup ready" or "skip") plus `preview_url` and `mockup_url` back to the sheet.
- Skips any business whose site it can't read properly, rather than making a generic page.
