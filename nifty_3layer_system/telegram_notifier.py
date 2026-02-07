"""
Telegram Bot Integration - Send Trading Levels to Telegram
Sends ML signals, levels, and option recommendations to Telegram
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ChatAction
import asyncio
from datetime import datetime
import pytz
from loguru import logger

# Import credentials from separate config file
try:
    from telegram_config import BOT_TOKEN, CHAT_ID
except ImportError:
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    CHAT_ID = os.getenv('CHAT_ID', '')

IST = pytz.timezone('Asia/Kolkata')


class TelegramNotifier:
    """Send trading signals to Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram bot
        
        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Your Telegram chat ID (get from @userinfobot)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
        
        if not bot_token or not chat_id:
            logger.error("❌ Missing Telegram credentials!")
            logger.error("   Get bot_token from @BotFather")
            logger.error("   Get chat_id from @userinfobot")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("✅ Telegram notifier initialized")
    
    async def send_message(self, message: str):
        """Send simple text message to Telegram"""
        if not self.enabled:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info("✅ Message sent to Telegram")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send message: {str(e)}")
            return False
    
    async def send_trading_signal(self, signal: dict):
        """Send formatted trading signal to Telegram"""
        if not self.enabled:
            return False
        
        try:
            # Format message
            direction = signal['ml']['direction']
            confidence = float(signal['ml']['confidence'])
            current_price = signal['current_price']
            timestamp = signal['timestamp'].strftime('%H:%M:%S')

            # Option-buy wording
            is_bullish = direction == 'BUY'
            action_label = 'CALL BUY' if is_bullish else 'PUT BUY'
            header_emoji = '🟢' if is_bullish else '🔴'

            # Confidence bar (10 blocks)
            filled = max(0, min(10, int(round(confidence / 10))))
            bar = "█" * filled + "░" * (10 - filled)

            message = f"""
{header_emoji} <b>{action_label} SIGNAL</b>  |  <i>{timestamp} IST</i>

<b>ML</b>  • Bias: {direction}  • Confidence: {confidence:.1f}%
<b>Confidence</b>: {bar} {confidence:.1f}%  • Spot: {current_price:,.2f}

<b>LEVELS</b>
• Entry: {signal.get('entry', 0):,.2f}
• Target: {signal.get('target', 0):,.2f}
• SL: {signal.get('sl', 0):,.2f}
• R:R: 1:{signal.get('rr', 0):.2f}

<b>Action</b>: {action_label}
"""
            
            await self.send_message(message)
            return True
            
        except Exception as e:
            logger.error(f"Error sending signal: {str(e)}")
            return False
    
    async def send_option_recommendation(self, option_data: dict):
        """Send option recommendation to Telegram"""
        if not self.enabled:
            return False
        
        try:
            strike = option_data['strike']
            option_type = option_data['option_type']
            premium = option_data['premium']
            volume = option_data['volume']
            oi = option_data['oi']
            
            message = f"""
<b>OPTION RECOMMENDATION</b>

<b>Strike:</b> {strike} {option_type}
<b>Entry Premium:</b> {premium:.2f}
<b>Liquidity:</b> Vol {volume:,} | OI {oi:,}

<b>Premium Levels:</b>
Target: {premium + 20:.2f} (+20)
SL: {premium - 15:.2f} (-15)

<b>P&L (65 contracts):</b>
Profit: +{(20 * 65):,}
Loss: -{(15 * 65):,}
"""
            
            await self.send_message(message)
            return True
            
        except Exception as e:
            logger.error(f"Error sending option data: {str(e)}")
            return False
    
    async def send_enhanced_signal(self, signal: dict):
        """Send enhanced signal with confluence scoring"""
        if not self.enabled:
            return False
        
        try:
            ml_conf = signal['ml']['confidence']
            confluence_pct = signal['confluence']['percentage']
            combined = signal['combined_confidence']
            action = signal['action']
            grade = signal['grade']
            
            # Emoji based on grade
            emoji_map = {'HIGH': 'OK', 'MEDIUM': 'CAUTION', 'LOW': 'SKIP'}
            emoji = emoji_map.get(grade, 'INFO')
            
            message = f"""
<b>{emoji} ENHANCED SIGNAL - {signal['timestamp'].strftime('%H:%M:%S')} IST</b>

<b>ML Prediction:</b>
Direction: {signal['ml']['direction']}
Confidence: {ml_conf:.2f}%

<b>Analyzer Validation:</b>
Confluence: {confluence_pct:.1f}%
Volume: {signal['confluence']['details']['volume']['status']}
Structure: {signal['confluence']['details']['structure']['status']}
EMA: {signal['confluence']['details']['ema']['status']}

<b>COMBINED: {combined:.2f}%</b>
<b>Grade: {grade}</b>
<b>Action: {action}</b>
"""
            
            await self.send_message(message)
            return True
            
        except Exception as e:
            logger.error(f"Error sending enhanced signal: {str(e)}")
            return False
    
    async def send_daily_summary(self, trades_today: int, pnl: float, win_count: int):
        """Send daily trading summary"""
        if not self.enabled:
            return False
        
        try:
            win_rate = (win_count / trades_today * 100) if trades_today > 0 else 0
            
            message = f"""
<b>DAILY SUMMARY - {datetime.now(IST).strftime('%d-%m-%Y')}</b>

Total Trades: {trades_today}
Wins: {win_count}
Losses: {trades_today - win_count}
Win Rate: {win_rate:.1f}%

<b>P&L:</b> {pnl:,.2f}
"""
            
            await self.send_message(message)
            return True
            
        except Exception as e:
            logger.error(f"Error sending summary: {str(e)}")
            return False


def setup_telegram():
    """Get Telegram credentials from user"""
    print("""
╔════════════════════════════════════════════════════════════════════╗
║           TELEGRAM BOT SETUP - GET YOUR CREDENTIALS               ║
╚════════════════════════════════════════════════════════════════════╝

Step 1: Create a Telegram Bot
   • Open Telegram and search for @BotFather
   • Send /start
   • Send /newbot
   • Follow instructions (pick a name and username)
   • BotFather will give you a TOKEN
   • Copy and save the TOKEN

Step 2: Get Your Chat ID
   • Search for @userinfobot on Telegram
   • Send /start
   • It will show your User ID (this is your CHAT_ID)
   • Copy and save the CHAT_ID

Step 3: Test the Bot
   • Go back to your bot (search by username)
   • Send /start message to activate it

Now enter your credentials:
""")
    
    bot_token = input("🤖 Enter Bot Token: ").strip()
    chat_id = input("💬 Enter Chat ID: ").strip()
    
    if bot_token and chat_id:
        print("\n✅ Credentials saved!")
        print("\nAdd to your config or environment:")
        print(f"BOT_TOKEN={bot_token}")
        print(f"CHAT_ID={chat_id}")
        return bot_token, chat_id
    else:
        print("❌ Invalid credentials")
        return None, None


async def test_telegram():
    """Test Telegram connection"""
    print("\n📡 Testing Telegram connection...\n")
    
    bot_token = os.getenv('BOT_TOKEN')
    chat_id = os.getenv('CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ Missing credentials. Run setup first:")
        print("   python telegram_notifier.py setup")
        return
    
    notifier = TelegramNotifier(bot_token, chat_id)
    
    if notifier.enabled:
        await notifier.send_message("✅ <b>Trading Bot Connected!</b>\n\nYou'll receive trading signals here.")
        print("✅ Test message sent to Telegram!")
    else:
        print("❌ Failed to initialize Telegram")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_telegram()
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_telegram())
    else:
        print("""
Usage:
  python telegram_notifier.py setup   - Setup Telegram credentials
  python telegram_notifier.py test    - Test Telegram connection
""")
