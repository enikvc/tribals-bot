# Tribals Bot Python - Project Overview

This is a sophisticated browser automation bot for Tribal Wars (online game) built with Python and Playwright.

## Architecture Overview

- **Modular design** with clear separation of concerns
- **Abstract base classes** for extensibility (BaseAutomation)
- **Event-driven architecture** using asyncio
- **Comprehensive anti-detection system**

## Key Components

### Core System (`src/core/`)
- **BrowserManager**: Manages stealth browser control with anti-detection measures
- **Scheduler**: Orchestrates automation tasks respecting active hours
- **ConfigManager**: YAML-based configuration management
- **LoginHandler**: Automated authentication with captcha support
- **BaseAutomation**: Abstract base class for all automation scripts

### Automation Scripts (`src/automations/`)
- **AutoBuyer**: Premium resource trading (speed-optimized, minimal stealth)
- **AutoFarmer**: Farm attack management using external farmgod.js script
- **AutoScavenger**: Scavenging expedition automation with jittered intervals

### Captcha System (`src/captcha/`)
- **CaptchaDetector**: Monitors all game pages for captcha challenges
- **CaptchaSolver**: AI-powered solving via Google Gemini API
- **Manual fallback**: Discord notifications when automatic solving fails
- **Anti-detection suspension**: Pauses stealth behaviors during solving

### Utilities (`src/utils/`)
- **AntiDetectionManager**: Coordinates human-like behavior simulation
- **HumanBehavior**: Bezier curve mouse movements, typing with typos, fatigue simulation
- **DiscordNotifier**: Real-time notifications via webhooks
- **ScreenshotManager**: Organized screenshot capture for debugging
- **Logger**: Comprehensive logging with emoji support

## Notable Features

### Anti-Detection Measures
- Uses real Chrome browser (not Chromium) for authenticity
- WebGL fingerprint spoofing
- Navigator.webdriver override
- Human-like interaction patterns:
  - Bezier curve mouse movements
  - Variable typing speeds with occasional typos
  - Reading pauses based on content length
  - Session fatigue simulation (slower actions over time)
  - Random breaks and idle movements

### Configuration
- YAML-based configuration (`config.yaml`)
- Environment variable support via `.env`
- Per-automation settings
- Active hours scheduling with sleep mode
- Discord webhook integration

### Project Structure
```
tribals-bot-python/
├── main.py              # Entry point
├── test.py              # hCaptcha testing tool
├── config.yaml          # Main configuration
├── requirements.txt     # Python dependencies
├── setup.py            # Installation script
└── src/
    ├── core/           # Core framework components
    ├── automations/    # Game-specific automation scripts
    ├── captcha/        # Captcha detection and solving
    └── utils/          # Helper utilities
```

## Important Commands

### Running the Bot
```bash
python main.py
```

### Testing Captcha Solver
```bash
python test.py
```

### Screenshot Cleanup
```bash
python src/utils/screenshot_cleanup.py --stats
python src/utils/screenshot_cleanup.py --cleanup 7
```

## Development Notes

- All automations inherit from `BaseAutomation` for consistent behavior
- Captcha detection runs continuously across all browser tabs
- Screenshots are automatically cleaned up after 7 days
- Discord notifications sent for critical events
- Browser data persisted in `browser_data/` directory
- External scripts downloaded to `vendor/` directory

## Security Considerations

- Credentials stored in environment variables
- No hardcoded sensitive data
- Session persistence for authentication
- Automatic logout handling
- Screenshot capture for debugging (may contain sensitive data)

## Dependencies

- Python 3.8+
- Playwright with Chrome browser
- Google Gemini API key (for captcha solving)
- Discord webhook URL (optional, for notifications)