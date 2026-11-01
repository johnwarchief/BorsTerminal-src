---
name: playwright-cli
description: Playwright CLI automation tool for browser automation, headless testing, interaction, screenshot capture, form filling, and tracing via CLI commands.
---

# Playwright CLI

Control browsers via the command line to perform automated tasks, testing, scraping, and web page interactions.

## Installation

```bash
# Install Playwright CLI
npm install -g @playwright/cli@latest

# Install skills (for AI agent usage)
playwright-cli install --skills

# Check version
playwright-cli --version
```

## Core Commands

### Browser Control

| Command | Description |
|---------|-------------|
| `playwright-cli open <url>` | Open browser and navigate to URL |
| `playwright-cli goto <url>` | Navigate to target URL |
| `playwright-cli close` | Close current page |
| `playwright-cli screenshot [ref]` | Capture screenshot (full page or target element) |
| `playwright-cli screenshot --filename=f` | Save screenshot to specific file |
| `playwright-cli pdf` | Save page as PDF |
| `playwright-cli pdf --filename=page.pdf` | Save PDF to specific file |
| `playwright-cli resize <w> <h>` | Resize browser viewport |
| `playwright-cli reload` | Reload current page |
| `playwright-cli go-back` | Navigate back |
| `playwright-cli go-forward` | Navigate forward |

### Page Interaction

| Command | Description |
|---------|-------------|
| `playwright-cli click <ref>` | Click element |
| `playwright-cli dblclick <ref>` | Double click element |
| `playwright-cli fill <ref> <text>` | Fill form input |
| `playwright-cli fill <ref> <text> --submit` | Fill input and press Enter |
| `playwright-cli type <text>` | Type text |
| `playwright-cli hover <ref>` | Hover mouse over element |
| `playwright-cli drag <startRef> <endRef>` | Drag and drop operation |
| `playwright-cli select <ref> <val>` | Select dropdown option |
| `playwright-cli check <ref>` | Check checkbox / radio button |
| `playwright-cli uncheck <ref>` | Uncheck checkbox |
| `playwright-cli upload <file>` | Upload file |
| `playwright-cli press <key>` | Press key (e.g., Enter, ArrowLeft) |

### Keyboard and Mouse

| Command | Description |
|---------|-------------|
| `playwright-cli keydown <key>` | Key down |
| `playwright-cli keyup <key>` | Key up |
| `playwright-cli mousemove <x> <y>` | Move mouse to coordinates |
| `playwright-cli mousedown [button]` | Mouse down |
| `playwright-cli mouseup [button]` | Mouse up |
| `playwright-cli mousewheel <dx> <dy>` | Scroll wheel |

### Element Locators

Supports multiple locator strategies:

```bash
# CSS Selector
playwright-cli click "#main > button.submit"

# Role Locator
playwright-cli click "getByRole('button', { name: 'Submit' })"

# Test ID
playwright-cli click "getByTestId('submit-button')"

# Snapshot reference (Recommended)
playwright-cli snapshot  # Capture snapshot containing element refs like e15
playwright-cli click e15  # Click target ref ID
```

### Snapshots

```bash
# Capture page snapshot (including element references)
playwright-cli snapshot

# Save snapshot to file
playwright-cli snapshot --filename=after-click.yaml

# Snapshot specific element
playwright-cli snapshot "#main"

# Limit snapshot depth
playwright-cli snapshot --depth=4
```

### Tab Management

```bash
playwright-cli tab-list    # List all tabs
playwright-cli tab-new [url]  # Open new tab
playwright-cli tab-close <index>  # Close tab by index
playwright-cli tab-select <index>  # Switch to tab by index
```

### Storage and State

**Cookies:**
```bash
playwright-cli cookie-list [--domain]  # List cookies
playwright-cli cookie-get <name>       # Get cookie
playwright-cli cookie-set <name> <val> # Set cookie
playwright-cli cookie-delete <name>    # Delete cookie
playwright-cli cookie-clear           # Clear all cookies
```

**LocalStorage:**
```bash
playwright-cli localstorage-list                   # List keys
playwright-cli localstorage-get <key>             # Get value
playwright-cli localstorage-set <k> <v>           # Set key-value
playwright-cli localstorage-delete <k>            # Delete key
playwright-cli localstorage-clear                 # Clear storage
```

**Save and Load State:**
```bash
playwright-cli state-save [filename]   # Save storage state
playwright-cli state-load <filename>   # Load storage state
```

### Network Interception

```bash
playwright-cli route <pattern> [opts]  # Intercept network requests
playwright-cli route-list              # List active routing rules
playwright-cli unroute [pattern]       # Remove routing rule
```

### Debugging Features

```bash
playwright-cli console [min-level]  # View console logs
playwright-cli network              # View network requests
playwright-cli run-code <code>      # Execute code snippet
playwright-cli run-code --filename=f  # Execute script file
```

### Tracing and Video Recording

```bash
playwright-cli tracing-start    # Start tracing
playwright-cli tracing-stop     # Stop tracing
playwright-cli video-start [filename]  # Start video recording
playwright-cli video-chapter <title>   # Add chapter mark
playwright-cli video-stop      # Stop video recording
```

### Browser Options

```bash
# Specific browser
playwright-cli open --browser=chrome  # chrome/firefox/webkit

# Headed mode (visible browser window)
playwright-cli open <url> --headed

# Persistent profile
playwright-cli open --persistent

# Configuration file
playwright-cli open --config=file.json

# Attach to existing running browser
playwright-cli attach --extension
```

## Session Management

```bash
# List all active sessions
playwright-cli list

# Close all browsers
playwright-cli close-all

# Force kill all browser processes
playwright-cli kill-all

# Visual dashboard
playwright-cli show

# Named sessions
playwright-cli -s=name open https://example.com  # Open in named session
playwright-cli -s=name close                    # Close named session
playwright-cli -s=name delete-data               # Delete session data
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PLAYWRIGHT_MCP_BROWSER` | Browser type | chrome |
| `PLAYWRIGHT_MCP_HEADLESS` | Headless mode | true |
| `PLAYWRIGHT_MCP_CONSOLE_LEVEL` | Console log level | info |
| `PLAYWRIGHT_MCP_TIMEOUT_ACTION` | Action timeout (ms) | 5000 |
| `PLAYWRIGHT_MCP_TIMEOUT_NAVIGATION` | Navigation timeout (ms) | 60000 |
| `PLAYWRIGHT_MCP_VIEWPORT_SIZE` | Viewport size | 1280x720 |
| `PLAYWRIGHT_MCP_OUTPUT_DIR` | Output directory | ./output |
| `PLAYWRIGHT_MCP_SAVE_VIDEO` | Save video | - |
| `PLAYWRIGHT_MCP_SAVE_TRACE` | Save trace | - |

## Usage Examples

### Basic Workflow

```bash
# 1. Open page
playwright-cli open https://demo.playwright.dev/todomvc/

# 2. Capture screenshot
playwright-cli screenshot

# 3. Fill todo items
playwright-cli type "Buy groceries"
playwright-cli press Enter
playwright-cli type "Water flowers"
playwright-cli press Enter

# 4. Check completed items
playwright-cli snapshot
playwright-cli check e21
playwright-cli check e35

# 5. Capture final screenshot
playwright-cli screenshot
```

### Configuration Example

Create `.playwright/cli.config.json`:

```json
{
  "browser": {
    "browserName": "chromium",
    "launchOptions": {
      "headless": false
    },
    "contextOptions": {
      "viewport": {
        "width": 1280,
        "height": 720
      }
    }
  },
  "outputDir": "./playwright-output",
  "outputMode": "file",
  "console": {
    "level": "info"
  },
  "timeouts": {
    "action": 5000,
    "navigation": 60000
  }
}
```

## Best Practices

1. Element references (e.g., `e15`) come from snapshots. After every DOM modification or navigation, capture a new snapshot.
2. Default execution is headless; pass `--headed` for interactive visual inspection.
3. Temporary profiles lose storage state upon closing; use `--persistent` or `state-save`/`state-load` when session persistence is required.