# 🎵 Pahari Music Bot

A feature-rich Telegram bot for music discovery and rating with personalized recommendations.

## 🎯 Features

### 🎵 Discovery Commands
- `/recommend` - Get today's song recommendation (deterministic daily pick, respects blacklist)
- `/random` - Get a completely random song (respects blacklist)
- `/discover` - **NEW!** Personalized recommendations based on your rating history
- `/similar` - **NEW!** Find songs similar to the last recommended one

### 🔍 Search & Filter
- `/genre [rock/metal/grunge]` - Filter songs by genre
- `/artist [name]` - Find songs by specific artist
- `/search [keyword]` - Search song titles

### ❤️ Personal Preferences & Ratings
- Rate songs using interactive polls (1-10 scale with emoji)
- `/favorite` - **FIXED!** Mark the last recommended song as favorite
- `/myfavorites` - List your favorite songs (explicit favorites + 8+ rated)
- `/blacklist` - **NEW!** Manage songs you never want to hear again
- `/myratings` - Show your complete rating history with star visualization

### 📊 Statistics & Community
- `/stats` - Show song ratings and popularity
- `/toprated` - Show highest-rated songs (7.0+ with 2+ votes)

### 🎮 Fun Features
- `/quote` - Get random music quotes
- `/trivia` - **NEW!** Music trivia quiz with multiple choice questions
- `/battle` - **NEW!** Song vs song voting battles (like "Black vs One")
- `/battlestats` - **NEW!** Battle leaderboard with win/loss records

### 🔧 Admin Commands
- `/add [title] [artist] [url] [genre] [year]` - Add new songs
- `/remove [song_id]` - Remove songs
- `/reload` - Reload song database

## 🚀 Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Setup:**
   ```bash
   cp env.example .env
   # Edit .env and add your TELEGRAM_BOT_TOKEN
   ```

3. **Admin Setup (Optional):**
   - Get your Telegram user ID from [@userinfobot](https://t.me/userinfobot)
   - Edit `bot.py` and add your ID to `ADMIN_USER_IDS = [YOUR_ID_HERE]`

4. **Run the Bot:**
   ```bash
   python bot.py
   ```

## 🎵 Song Database Format

Songs are stored in `songs.json` with the following structure:

```json
{
  "id": 1,
  "title": "Song Title",
  "artist": "Artist Name",
  "url": "https://youtube.com/watch?v=...",
  "genre": "rock",
  "year": 2024
}
```

## 💾 Data Storage

- **`songs.json`** - Song database
- **`user_data.json`** - User ratings and preferences
- **`quotes.json`** - Music quotes database

## 🎛️ Rating System

- Users rate songs 1-10 using interactive polls
- Ratings are tracked per user and song
- Statistics show average ratings and vote counts
- "Top Rated" requires minimum 2 votes and 7.0+ average

## 🎨 Enhanced Features

### Smart Filtering
- Genre filtering with available genre listing
- Artist search with partial matching
- Title search with multiple results display

### User Experience
- Rich song information display (genre, year)
- Emoji-enhanced interface
- Comprehensive help system
- Error handling and user feedback

### Admin Tools
- Easy song management
- Database reloading
- Permission-based access control

## 🛠️ Commands Overview

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Show help and available commands | |
| `/recommend` | Today's deterministic pick | |
| `/random` | Completely random song | |
| `/genre rock` | Random rock song | `/genre metal` |
| `/artist metallica` | Songs by Metallica | `/artist pearl jam` |
| `/search black` | Songs with "black" in title | `/search spirit` |
| `/myfavorites` | Your 8+ rated songs | |
| `/myratings` | All your ratings | |
| `/stats` | All song statistics | |
| `/toprated` | Community favorites | |
| `/quote` | Random music quote | |
| `/battle` | Song vs song voting | |
| `/battlestats` | Battle leaderboard | |

**Admin only:**
| Command | Description | Example |
|---------|-------------|---------|
| `/add` | Add new song | `/add "Song Title" "Artist" "URL" "genre" 2024` |
| `/remove` | Remove song by ID | `/remove 15` |
| `/reload` | Reload database | |

## 🎮 Usage Tips

1. **Smart Discovery:** Use `/discover` for AI-powered recommendations based on your taste
2. **Exploration:** Use `/random`, `/genre`, and `/similar` to explore music
3. **Preference Management:** Rate songs, use `/favorite`, and manage your `/blacklist`
4. **Social Features:** Check `/toprated` for community favorites and try `/trivia`
5. **Context Awareness:** All recommendation commands now track your last song for `/favorite`, `/blacklist`, and `/similar`

## 🎯 Smart Features

### **Personalized Intelligence**
- **Blacklist System:** Songs you blacklist are automatically filtered from all recommendations
- **Context Tracking:** Bot remembers your last song for easy favoriting and similarity search
- **Smart Discovery:** `/discover` analyzes your ratings to find genres and artists you love
- **Preference Learning:** Higher-rated songs influence future `/discover` recommendations

### **Enhanced User Experience**
- **Emoji-Rich Polls:** Beautiful 1️⃣-🔟 rating system
- **Dual Favorites:** Both explicit favorites (`/favorite`) and high ratings (8+) in `/myfavorites`
- **Smart Trivia:** Dynamic quiz questions based on your song database
- **Song Battles:** Head-to-head voting with win/loss tracking and leaderboards
- **Contextual Commands:** `/similar` works with your last recommendation

## 🔮 Future Enhancements

- Group voting and battles
- Lyrics integration (/lyrics command)
- Playlist creation
- Advanced statistics and analytics
- User collaboration features

---

Enjoy discovering music with Pahari Bot! 🎶
