# Instagram Automation System

A modular and configurable system for automating Instagram engagement tasks using Browser-Use and LangChain.

## Features

- **Target Audience Discovery**
  - Find relevant users through hashtag exploration
  - Analyze competitor followers
  - Smart filtering for quality engagement

- **Engagement Actions**
  - Follow users (up to 200/day)
  - Like posts (up to 200/day)
  - Comment on posts (up to 200/day)
  - All actions respect Instagram's rate limits

- **Smart Engagement**
  - Engage with content before following users
  - Generate contextual comments using LLM
  - Randomized delays between actions
  - Batch processing to simulate human behavior

- **Tracking & Analytics**
  - Detailed daily statistics
  - Success rate tracking
  - Error logging
  - Resume capability for interrupted sessions

## Installation

1. Ensure you have Python 3.8+ installed
2. Install the required packages:
   ```bash
   pip install browser-use langchain-openai python-dotenv
   ```

## Configuration

1. Create a `.env` file in your project root with your credentials:
   ```env
   INSTAGRAM_USERNAME=your_username
   INSTAGRAM_PASSWORD=your_password
   OPENAI_API_KEY=your_openai_api_key
   ```

2. Customize settings in `config.py`:
   - Daily action limits
   - Target hashtags
   - Competitor accounts
   - Comment templates
   - Timing intervals

## Usage

### Basic Usage

Run the automation with default settings:
```bash
python -m mytests.instagram_implementation.main
```

### Command Line Options

- Run in headless mode:
  ```bash
  python -m mytests.instagram_implementation.main --headless
  ```

- Resume from a previous session:
  ```bash
  python -m mytests.instagram_implementation.main --resume logs/instagram_stats_2024-03-14.json
  ```

## Directory Structure

```
instagram_implementation/
├── __init__.py
├── main.py              # Entry point
├── config.py            # Configuration settings
├── daily_tasks.py       # Task orchestration
├── strategy/
│   ├── find_audience.py # User discovery
│   ├── follow_users.py  # Following logic
│   ├── like_posts.py    # Liking logic
│   ├── comment_posts.py # Commenting logic
│   └── timing.py        # Delay management
├── logs/                # Statistics and logs
└── README.md           # Documentation
```

## Safety Features

1. **Rate Limiting**
   - Enforced daily limits
   - Random delays between actions
   - Batch processing with intervals

2. **Error Handling**
   - Graceful error recovery
   - Session resumption
   - Detailed error logging

3. **Human-like Behavior**
   - Natural engagement patterns
   - Contextual commenting
   - Random variations in timing

## Best Practices

1. **Account Safety**
   - Start with lower daily limits
   - Gradually increase activity
   - Monitor for any warning signs

2. **Content Quality**
   - Engage with relevant content
   - Generate meaningful comments
   - Follow active, real users

3. **System Usage**
   - Run during your typical active hours
   - Use a stable internet connection
   - Monitor the logs regularly

## Logging

Logs and statistics are saved in the `logs/` directory:
- Daily statistics in JSON format
- Error logs with timestamps
- Success/failure tracking

## Development

### Adding New Features

1. Create new modules in the `strategy/` directory
2. Update `daily_tasks.py` to incorporate new functionality
3. Add configuration options to `config.py`

### Testing

Run the system with `--headless=False` initially to monitor behavior.

## Troubleshooting

1. **Login Issues**
   - Verify credentials in `.env`
   - Check for Instagram security prompts
   - Ensure no active sessions elsewhere

2. **Rate Limits**
   - Review daily statistics
   - Adjust timing parameters
   - Decrease batch sizes

3. **Browser Issues**
   - Update Browser-Use
   - Clear browser cache/cookies
   - Check internet connection

## Disclaimer

This tool is for educational purposes. Use responsibly and in accordance with Instagram's terms of service. The authors are not responsible for any account restrictions or bans resulting from its use.

## License

MIT License - See LICENSE file for details. 