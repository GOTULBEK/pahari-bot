import json
import logging
import os
import random
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from telegram import Update, PollAnswer
from telegram.ext import ApplicationBuilder, Application, CommandHandler, MessageHandler, PollAnswerHandler, filters, ContextTypes


PROJECT_DIR = Path(__file__).resolve().parent
SONGS_FILE = PROJECT_DIR / "songs.json"
USER_DATA_FILE = PROJECT_DIR / "user_data.json"
QUOTES_FILE = PROJECT_DIR / "quotes.json"

# Admin user IDs (add your Telegram user ID here)
# To get your user ID, send a message to @userinfobot on Telegram
# Example: ADMIN_USER_IDS = [123456789, 987654321]
ADMIN_USER_IDS = [2100114055]  # Add your user ID to enable admin commands


def load_songs() -> List[Dict[str, Any]]:
    try:
        with open(SONGS_FILE, "r", encoding="utf-8") as f:
            songs = json.load(f)
            logging.info(f"Loaded {len(songs)} songs from {SONGS_FILE}")
            return songs
    except FileNotFoundError:
        logging.error(f"Songs file not found: {SONGS_FILE}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in songs file: {e}")
        return []
    except Exception as e:
        logging.error(f"Error loading songs: {e}")
        return []


def load_user_data() -> Dict[str, Any]:
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.info("User data file not found, creating new one")
        return {"users": {}, "ratings": {}, "groups": {}, "favorites": {}, "blacklist": {}, "last_songs": {}, "battles": {}}
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in user data file: {e}")
        return {"users": {}, "ratings": {}, "groups": {}, "favorites": {}, "blacklist": {}, "last_songs": {}, "battles": {}}
    except Exception as e:
        logging.error(f"Error loading user data: {e}")
        return {"users": {}, "ratings": {}, "groups": {}, "favorites": {}, "blacklist": {}, "last_songs": {}, "battles": {}}


def save_user_data(data: Dict[str, Any]) -> None:
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving user data: {e}")


def load_quotes() -> List[str]:
    try:
        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Quotes file not found: {QUOTES_FILE}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in quotes file: {e}")
        return []
    except Exception as e:
        logging.error(f"Error loading quotes: {e}")
        return []


def get_today_index(num_songs: int) -> int:
    # Deterministic per-day index based on days since a fixed epoch
    base = date(2024, 1, 1)
    today = date.today()
    delta_days = (today - base).days
    if num_songs == 0:
        return 0
    return delta_days % num_songs


def format_song_message(song: Dict[str, Any], prefix: str = "Today's pick") -> str:
    title = song.get("title", "Unknown Title")
    artist = song.get("artist", "Unknown Artist")
    genre = song.get("genre", "Unknown")
    year = song.get("year", "Unknown")
    url = song.get("url")
    
    message = f"{prefix}: {title} — {artist}\n"
    message += f"🎵 Genre: {genre} | Year: {year}"
    
    if url:
        message += f"\n{url}"
    return message


def track_last_song(user_id: str, song: Dict[str, Any]) -> None:
    """Track the last song sent to a user for context."""
    user_data = load_user_data()
    if "last_songs" not in user_data:
        user_data["last_songs"] = {}
    
    user_data["last_songs"][user_id] = {
        "song_id": song.get("id"),
        "title": song.get("title"),
        "artist": song.get("artist"),
        "timestamp": datetime.now().isoformat()
    }
    save_user_data(user_data)


def get_user_blacklist(user_id: str) -> List[int]:
    """Get user's blacklisted song IDs."""
    user_data = load_user_data()
    return user_data.get("blacklist", {}).get(user_id, [])


def filter_blacklisted_songs(songs: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    """Filter out blacklisted songs for a user."""
    blacklist = get_user_blacklist(user_id)
    return [song for song in songs if song.get("id") not in blacklist]


async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user_id = str(update.effective_user.id)
    logging.info(f"Received /recommend command from user {update.effective_user.id} in {chat.type} chat {chat.id}")
    try:
        songs = load_songs()
        if not songs:
            logging.warning("No songs available")
            await update.effective_message.reply_text("No songs available yet.")
            return

        # Filter out blacklisted songs
        filtered_songs = filter_blacklisted_songs(songs, user_id)
        if not filtered_songs:
            await update.effective_message.reply_text("All songs are in your blacklist! Use /blacklist to manage your preferences.")
            return

        idx = get_today_index(len(filtered_songs))
        logging.info(f"Selected song index {idx} out of {len(filtered_songs)} songs")
        
        if idx >= len(filtered_songs):
            logging.error(f"Index {idx} is out of range for {len(filtered_songs)} songs")
            await update.effective_message.reply_text("Error: Song index out of range. Please check the songs list.")
            return
            
        song = filtered_songs[idx]
        logging.info(f"Recommending song: {song.get('title', 'Unknown')} by {song.get('artist', 'Unknown')}")

        # Track this song for the user
        track_last_song(user_id, song)

        # Send the song info
        text = format_song_message(song)
        message = await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

        # Send a non-anonymous poll for rating 1-10
        options = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        question = f"Rate today's song: {song.get('title', 'Unknown Title')}"
        poll = await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=question,
            options=options,
            allows_multiple_answers=False,
            is_anonymous=False,
        )
        
        # Store poll context for rating tracking
        context.bot_data[f"poll_{poll.poll.id}"] = {
            "song_id": song.get("id"),
            "song_title": song.get("title"),
            "chat_id": update.effective_chat.id
        }
    except Exception as e:
        logging.error(f"Error in recommend command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred while getting today's recommendation. Please try again later.")
        
        # Log the stack trace for debugging
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")


async def random_song(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a completely random song."""
    chat = update.effective_chat
    user_id = str(update.effective_user.id)
    logging.info(f"Received /random command from user {update.effective_user.id}")
    
    try:
        songs = load_songs()
        if not songs:
            await update.effective_message.reply_text("No songs available yet.")
            return
        
        # Filter out blacklisted songs
        filtered_songs = filter_blacklisted_songs(songs, user_id)
        if not filtered_songs:
            await update.effective_message.reply_text("All songs are in your blacklist! Use /blacklist to manage your preferences.")
            return
        
        song = random.choice(filtered_songs)
        track_last_song(user_id, song)
        
        text = format_song_message(song, "Random pick")
        message = await context.bot.send_message(chat_id=chat.id, text=text)
        
        # Send rating poll
        await send_rating_poll(context, chat.id, song)
        
    except Exception as e:
        logging.error(f"Error in random command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def genre_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Filter songs by genre."""
    chat = update.effective_chat
    user_id = update.effective_user.id
    logging.info(f"Received /genre command from user {user_id}")
    
    try:
        args = context.args
        if not args:
            songs = load_songs()
            genres = list(set(song.get("genre", "unknown").lower() for song in songs))
            await update.effective_message.reply_text(f"Available genres: {', '.join(sorted(genres))}\nUsage: /genre [genre_name]")
            return
        
        genre = args[0].lower()
        songs = load_songs()
        filtered_songs = [song for song in songs if song.get("genre", "").lower() == genre]
        
        if not filtered_songs:
            await update.effective_message.reply_text(f"No songs found for genre: {genre}")
            return
        
        song = random.choice(filtered_songs)
        track_last_song(str(user_id), song)
        text = format_song_message(song, f"{genre.title()} pick")
        await context.bot.send_message(chat_id=chat.id, text=text)
        await send_rating_poll(context, chat.id, song)
        
    except Exception as e:
        logging.error(f"Error in genre command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def artist_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Find songs by specific artist."""
    chat = update.effective_chat
    user_id = update.effective_user.id
    logging.info(f"Received /artist command from user {user_id}")
    
    try:
        args = context.args
        if not args:
            await update.effective_message.reply_text("Usage: /artist [artist_name]")
            return
        
        artist_name = " ".join(args).lower()
        songs = load_songs()
        artist_songs = [song for song in songs if artist_name in song.get("artist", "").lower()]
        
        if not artist_songs:
            await update.effective_message.reply_text(f"No songs found for artist: {' '.join(args)}")
            return
        
        if len(artist_songs) == 1:
            song = artist_songs[0]
            text = format_song_message(song, f"By {song.get('artist')}")
        else:
            song = random.choice(artist_songs)
            text = format_song_message(song, f"Random from {song.get('artist')} ({len(artist_songs)} available)")
        
        track_last_song(str(user_id), song)
        await context.bot.send_message(chat_id=chat.id, text=text)
        await send_rating_poll(context, chat.id, song)
        
    except Exception as e:
        logging.error(f"Error in artist command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def search_songs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search song titles."""
    chat = update.effective_chat
    user_id = update.effective_user.id
    logging.info(f"Received /search command from user {user_id}")
    
    try:
        args = context.args
        if not args:
            await update.effective_message.reply_text("Usage: /search [keyword]")
            return
        
        keyword = " ".join(args).lower()
        songs = load_songs()
        matching_songs = [song for song in songs if keyword in song.get("title", "").lower()]
        
        if not matching_songs:
            await update.effective_message.reply_text(f"No songs found with keyword: {' '.join(args)}")
            return
        
        if len(matching_songs) == 1:
            song = matching_songs[0]
            track_last_song(str(user_id), song)
            text = format_song_message(song, "Search result")
            await context.bot.send_message(chat_id=chat.id, text=text)
            await send_rating_poll(context, chat.id, song)
        else:
            # Show multiple results
            result_text = f"Found {len(matching_songs)} songs matching '{' '.join(args)}':\n\n"
            for i, song in enumerate(matching_songs[:10], 1):  # Limit to 10 results
                result_text += f"{i}. {song.get('title')} — {song.get('artist')}\n"
            
            if len(matching_songs) > 10:
                result_text += f"\n... and {len(matching_songs) - 10} more"
            
            await update.effective_message.reply_text(result_text)
        
    except Exception as e:
        logging.error(f"Error in search command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def favorite_song(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mark last recommended song as favorite."""
    user_id = str(update.effective_user.id)
    logging.info(f"Received /favorite command from user {user_id}")
    
    try:
        user_data = load_user_data()
        last_songs = user_data.get("last_songs", {})
        
        if user_id not in last_songs:
            await update.effective_message.reply_text("No recent song to favorite! Use /recommend, /random, or other commands first.")
            return
        
        last_song = last_songs[user_id]
        song_id = str(last_song.get("song_id"))
        song_title = last_song.get("title", "Unknown")
        song_artist = last_song.get("artist", "Unknown")
        
        # Add to favorites
        if "favorites" not in user_data:
            user_data["favorites"] = {}
        if user_id not in user_data["favorites"]:
            user_data["favorites"][user_id] = []
        
        if song_id not in user_data["favorites"][user_id]:
            user_data["favorites"][user_id].append(song_id)
            save_user_data(user_data)
            await update.effective_message.reply_text(f"❤️ Added to favorites: {song_title} — {song_artist}")
        else:
            await update.effective_message.reply_text(f"💖 Already in favorites: {song_title} — {song_artist}")
        
    except Exception as e:
        logging.error(f"Error in favorite command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def my_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List user's favorite songs."""
    user_id = str(update.effective_user.id)
    logging.info(f"Received /myfavorites command from user {user_id}")
    
    try:
        user_data = load_user_data()
        
        # Get explicit favorites
        favorites = user_data.get("favorites", {}).get(user_id, [])
        
        # Get highly rated songs (8+)
        ratings = user_data.get("ratings", {})
        user_ratings = {song_id: rating for song_id, users in ratings.items() 
                       if user_id in users for rating in [users[user_id]] if rating >= 8}
        
        # Combine favorites and high ratings
        all_favorites = set(favorites + list(user_ratings.keys()))
        
        if not all_favorites:
            await update.effective_message.reply_text("No favorites yet! Use /favorite to mark songs or rate them 8+ ⭐")
            return
        
        songs = load_songs()
        song_dict = {str(song.get("id")): song for song in songs}
        
        result_text = "❤️ Your Favorite Songs:\n\n"
        
        # Show explicit favorites first
        if favorites:
            result_text += "💖 Explicitly Favorited:\n"
            for song_id in favorites:
                if song_id in song_dict:
                    song = song_dict[song_id]
                    rating_text = f" ({user_ratings[song_id]}/10)" if song_id in user_ratings else ""
                    result_text += f"❤️ {song.get('title')} — {song.get('artist')}{rating_text}\n"
            result_text += "\n"
        
        # Show highly rated songs
        high_rated = {sid: rating for sid, rating in user_ratings.items() if sid not in favorites}
        if high_rated:
            result_text += "⭐ Highly Rated (8+):\n"
            for song_id, rating in sorted(high_rated.items(), key=lambda x: x[1], reverse=True):
                if song_id in song_dict:
                    song = song_dict[song_id]
                    result_text += f"⭐ {rating}/10 - {song.get('title')} — {song.get('artist')}\n"
        
        await update.effective_message.reply_text(result_text)
        
    except Exception as e:
        logging.error(f"Error in myfavorites command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show song ratings and popularity."""
    logging.info(f"Received /stats command from user {update.effective_user.id}")
    
    try:
        user_data = load_user_data()
        ratings = user_data.get("ratings", {})
        
        if not ratings:
            await update.effective_message.reply_text("No ratings available yet. Start rating some songs!")
            return
        
        songs = load_songs()
        song_dict = {str(song.get("id")): song for song in songs}
        
        # Calculate average ratings
        song_stats = {}
        for song_id, users in ratings.items():
            if song_id in song_dict:
                ratings_list = list(users.values())
                avg_rating = sum(ratings_list) / len(ratings_list)
                song_stats[song_id] = {
                    "avg_rating": avg_rating,
                    "vote_count": len(ratings_list),
                    "song": song_dict[song_id]
                }
        
        if not song_stats:
            await update.effective_message.reply_text("No valid ratings found.")
            return
        
        # Sort by average rating, then by vote count
        sorted_stats = sorted(song_stats.items(), 
                             key=lambda x: (x[1]["avg_rating"], x[1]["vote_count"]), 
                             reverse=True)
        
        result_text = "📊 Song Statistics:\n\n"
        for i, (song_id, stats) in enumerate(sorted_stats[:10], 1):
            song = stats["song"]
            result_text += f"{i}. {song.get('title')} — {song.get('artist')}\n"
            result_text += f"   ⭐ {stats['avg_rating']:.1f}/10 ({stats['vote_count']} votes)\n\n"
        
        await update.effective_message.reply_text(result_text)
        
    except Exception as e:
        logging.error(f"Error in stats command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def top_rated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show highest-rated songs."""
    logging.info(f"Received /toprated command from user {update.effective_user.id}")
    
    try:
        user_data = load_user_data()
        ratings = user_data.get("ratings", {})
        
        if not ratings:
            await update.effective_message.reply_text("No ratings available yet. Start rating some songs!")
            return
        
        songs = load_songs()
        song_dict = {str(song.get("id")): song for song in songs}
        
        # Calculate average ratings (minimum 2 votes)
        song_stats = {}
        for song_id, users in ratings.items():
            if song_id in song_dict and len(users) >= 2:
                ratings_list = list(users.values())
                avg_rating = sum(ratings_list) / len(ratings_list)
                song_stats[song_id] = {
                    "avg_rating": avg_rating,
                    "vote_count": len(ratings_list),
                    "song": song_dict[song_id]
                }
        
        if not song_stats:
            await update.effective_message.reply_text("Not enough ratings yet (need at least 2 votes per song).")
            return
        
        # Sort by average rating (minimum rating 7.0)
        top_songs = sorted(song_stats.items(), 
                          key=lambda x: x[1]["avg_rating"], 
                          reverse=True)
        top_songs = [(sid, stats) for sid, stats in top_songs if stats["avg_rating"] >= 7.0]
        
        if not top_songs:
            await update.effective_message.reply_text("No songs with 7.0+ average rating yet.")
            return
        
        result_text = "🏆 Top Rated Songs (7.0+):\n\n"
        for i, (song_id, stats) in enumerate(top_songs[:10], 1):
            song = stats["song"]
            result_text += f"{i}. {song.get('title')} — {song.get('artist')}\n"
            result_text += f"   ⭐ {stats['avg_rating']:.1f}/10 ({stats['vote_count']} votes)\n\n"
        
        await update.effective_message.reply_text(result_text)
        
    except Exception as e:
        logging.error(f"Error in toprated command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def my_ratings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's rating history."""
    user_id = str(update.effective_user.id)
    logging.info(f"Received /myratings command from user {user_id}")
    
    try:
        user_data = load_user_data()
        ratings = user_data.get("ratings", {})
        user_ratings = {song_id: users[user_id] for song_id, users in ratings.items() if user_id in users}
        
        if not user_ratings:
            await update.effective_message.reply_text("You haven't rated any songs yet! Use /recommend or /random to discover music.")
            return
        
        songs = load_songs()
        song_dict = {str(song.get("id")): song for song in songs}
        
        result_text = f"🎭 Your Ratings ({len(user_ratings)} songs):\n\n"
        for song_id, rating in sorted(user_ratings.items(), key=lambda x: x[1], reverse=True):
            if song_id in song_dict:
                song = song_dict[song_id]
                stars = "⭐" * rating
                result_text += f"{stars} {rating}/10 - {song.get('title')} — {song.get('artist')}\n"
        
        await update.effective_message.reply_text(result_text)
        
    except Exception as e:
        logging.error(f"Error in myratings command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random music quote."""
    logging.info(f"Received /quote command from user {update.effective_user.id}")
    
    try:
        quotes = load_quotes()
        if not quotes:
            await update.effective_message.reply_text("No quotes available.")
            return
        
        quote = random.choice(quotes)
        await update.effective_message.reply_text(f"🎵 {quote}")
        
    except Exception as e:
        logging.error(f"Error in quote command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage blacklisted songs."""
    user_id = str(update.effective_user.id)
    logging.info(f"Received /blacklist command from user {user_id}")
    
    try:
        args = context.args
        user_data = load_user_data()
        
        if not args:
            # Show current blacklist
            blacklist = user_data.get("blacklist", {}).get(user_id, [])
            if not blacklist:
                await update.effective_message.reply_text("Your blacklist is empty!\n\nTo blacklist the last recommended song: /blacklist add\nTo remove from blacklist: /blacklist remove [song_id]")
                return
            
            songs = load_songs()
            song_dict = {str(song.get("id")): song for song in songs}
            
            result_text = "🚫 Your Blacklisted Songs:\n\n"
            for song_id in blacklist:
                if str(song_id) in song_dict:
                    song = song_dict[str(song_id)]
                    result_text += f"🚫 ID:{song_id} - {song.get('title')} — {song.get('artist')}\n"
            
            result_text += f"\nTo remove: /blacklist remove [song_id]"
            await update.effective_message.reply_text(result_text)
            return
        
        action = args[0].lower()
        
        if action == "add":
            # Add last song to blacklist
            last_songs = user_data.get("last_songs", {})
            if user_id not in last_songs:
                await update.effective_message.reply_text("No recent song to blacklist! Use /recommend, /random, or other commands first.")
                return
            
            last_song = last_songs[user_id]
            song_id = last_song.get("song_id")
            song_title = last_song.get("title", "Unknown")
            song_artist = last_song.get("artist", "Unknown")
            
            if "blacklist" not in user_data:
                user_data["blacklist"] = {}
            if user_id not in user_data["blacklist"]:
                user_data["blacklist"][user_id] = []
            
            if song_id not in user_data["blacklist"][user_id]:
                user_data["blacklist"][user_id].append(song_id)
                save_user_data(user_data)
                await update.effective_message.reply_text(f"🚫 Blacklisted: {song_title} — {song_artist}\nThis song will not be recommended to you again.")
            else:
                await update.effective_message.reply_text(f"Already blacklisted: {song_title} — {song_artist}")
                
        elif action == "remove":
            if len(args) < 2 or not args[1].isdigit():
                await update.effective_message.reply_text("Usage: /blacklist remove [song_id]")
                return
            
            song_id = int(args[1])
            blacklist = user_data.get("blacklist", {}).get(user_id, [])
            
            if song_id in blacklist:
                user_data["blacklist"][user_id].remove(song_id)
                save_user_data(user_data)
                
                # Get song info
                songs = load_songs()
                song = next((s for s in songs if s.get("id") == song_id), None)
                if song:
                    await update.effective_message.reply_text(f"✅ Removed from blacklist: {song.get('title')} — {song.get('artist')}")
                else:
                    await update.effective_message.reply_text(f"✅ Removed song ID {song_id} from blacklist")
            else:
                await update.effective_message.reply_text(f"Song ID {song_id} is not in your blacklist.")
        else:
            await update.effective_message.reply_text("Usage:\n/blacklist - Show blacklisted songs\n/blacklist add - Blacklist last song\n/blacklist remove [song_id] - Remove from blacklist")
        
    except Exception as e:
        logging.error(f"Error in blacklist command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def discover_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get personalized song recommendations based on listening history."""
    user_id = str(update.effective_user.id)
    logging.info(f"Received /discover command from user {user_id}")
    
    try:
        user_data = load_user_data()
        ratings = user_data.get("ratings", {})
        user_ratings = {song_id: rating for song_id, users in ratings.items() if user_id in users}
        
        if len(user_ratings) < 3:
            await update.effective_message.reply_text("🔍 Need more data for personalized recommendations!\n\nRate at least 3 songs first using /recommend or /random, then try /discover again.")
            return
        
        songs = load_songs()
        song_dict = {str(song.get("id")): song for song in songs}
        
        # Find user preferences
        high_rated_songs = {sid: rating for sid, rating in user_ratings.items() if rating >= 7}
        preferred_genres = {}
        preferred_artists = {}
        
        for song_id, rating in high_rated_songs.items():
            if song_id in song_dict:
                song = song_dict[song_id]
                genre = song.get("genre", "").lower()
                artist = song.get("artist", "").lower()
                
                if genre:
                    preferred_genres[genre] = preferred_genres.get(genre, 0) + rating
                if artist:
                    preferred_artists[artist] = preferred_artists.get(artist, 0) + rating
        
        # Filter songs by preferences and blacklist
        filtered_songs = filter_blacklisted_songs(songs, user_id)
        unrated_songs = [song for song in filtered_songs if str(song.get("id")) not in user_ratings]
        
        if not unrated_songs:
            await update.effective_message.reply_text("🎉 You've rated all available songs! Check /toprated for community favorites.")
            return
        
        # Score songs based on preferences
        scored_songs = []
        for song in unrated_songs:
            score = 0
            genre = song.get("genre", "").lower()
            artist = song.get("artist", "").lower()
            
            if genre in preferred_genres:
                score += preferred_genres[genre] * 0.7
            if artist in preferred_artists:
                score += preferred_artists[artist] * 0.9
            
            scored_songs.append((song, score))
        
        # Sort by score and add some randomness
        scored_songs.sort(key=lambda x: x[1], reverse=True)
        
        # Pick from top 30% or top 5, whichever is larger
        top_count = max(5, len(scored_songs) // 3)
        top_songs = [song for song, score in scored_songs[:top_count]]
        
        if top_songs:
            song = random.choice(top_songs)
            track_last_song(user_id, song)
            
            # Show discovery reasoning
            genre = song.get("genre", "").lower()
            artist = song.get("artist", "").lower()
            reasons = []
            if genre in preferred_genres:
                reasons.append(f"you like {genre}")
            if artist in preferred_artists:
                reasons.append(f"you like {artist}")
            
            reason_text = f" (recommended because {', '.join(reasons)})" if reasons else " (exploring new territory for you)"
            
            text = format_song_message(song, f"🔍 Discovered for you{reason_text}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            await send_rating_poll(context, update.effective_chat.id, song)
        else:
            # Fallback to random unrated song
            song = random.choice(unrated_songs)
            track_last_song(user_id, song)
            text = format_song_message(song, "🔍 Random discovery")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            await send_rating_poll(context, update.effective_chat.id, song)
        
    except Exception as e:
        logging.error(f"Error in discover command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def similar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Find songs similar to the last recommended song."""
    user_id = str(update.effective_user.id)
    logging.info(f"Received /similar command from user {user_id}")
    
    try:
        user_data = load_user_data()
        last_songs = user_data.get("last_songs", {})
        
        if user_id not in last_songs:
            await update.effective_message.reply_text("No recent song to find similar to! Use /recommend, /random, or other commands first.")
            return
        
        last_song_id = str(last_songs[user_id].get("song_id"))
        songs = load_songs()
        
        # Find the reference song
        reference_song = None
        for song in songs:
            if str(song.get("id")) == last_song_id:
                reference_song = song
                break
        
        if not reference_song:
            await update.effective_message.reply_text("Could not find the reference song. Try another command first.")
            return
        
        # Find similar songs (same genre or artist)
        ref_genre = reference_song.get("genre", "").lower()
        ref_artist = reference_song.get("artist", "").lower()
        
        similar_songs = []
        for song in songs:
            if str(song.get("id")) == last_song_id:
                continue  # Skip the same song
            
            genre = song.get("genre", "").lower()
            artist = song.get("artist", "").lower()
            
            # Exact artist match gets priority
            if artist == ref_artist:
                similar_songs.append((song, 2))
            # Same genre gets lower priority
            elif genre == ref_genre:
                similar_songs.append((song, 1))
        
        # Filter blacklisted songs
        filtered_similar = [(song, priority) for song, priority in similar_songs 
                           if song.get("id") not in get_user_blacklist(user_id)]
        
        if not filtered_similar:
            await update.effective_message.reply_text(f"No similar songs found to {reference_song.get('title')} by {reference_song.get('artist')}.")
            return
        
        # Sort by priority (artist matches first, then genre)
        filtered_similar.sort(key=lambda x: x[1], reverse=True)
        
        # Pick a random song from the similar ones
        song, priority = random.choice(filtered_similar)
        track_last_song(user_id, song)
        
        similarity_reason = "same artist" if priority == 2 else "same genre"
        prefix = f"🎭 Similar to {reference_song.get('title')} ({similarity_reason})"
        
        text = format_song_message(song, prefix)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        await send_rating_poll(context, update.effective_chat.id, song)
        
    except Exception as e:
        logging.error(f"Error in similar command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def trivia_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Music trivia questions."""
    logging.info(f"Received /trivia command from user {update.effective_user.id}")
    
    try:
        songs = load_songs()
        if len(songs) < 4:
            await update.effective_message.reply_text("Need at least 4 songs for trivia!")
            return
        
        # Pick a random song for the question
        correct_song = random.choice(songs)
        
        # Create multiple choice options
        wrong_songs = [song for song in songs if song.get("id") != correct_song.get("id")]
        wrong_options = random.sample(wrong_songs, min(3, len(wrong_songs)))
        
        all_options = [correct_song] + wrong_options
        random.shuffle(all_options)
        
        # Find correct answer index
        correct_index = all_options.index(correct_song)
        
        # Create question
        question_types = [
            f"🎵 Which song is by {correct_song.get('artist')}?",
            f"🎸 Which song is from the {correct_song.get('genre', 'unknown')} genre?",
            f"📅 Which song was released in {correct_song.get('year', 'unknown')}?"
        ]
        
        question = random.choice(question_types)
        options = [f"{song.get('title')}" for song in all_options]
        
        # Send poll
        poll = await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=question,
            options=options,
            type="quiz",
            correct_option_id=correct_index,
            explanation=f"Correct! {correct_song.get('title')} by {correct_song.get('artist')} ({correct_song.get('genre')}, {correct_song.get('year')})",
            allows_multiple_answers=False,
            is_anonymous=False,
        )
        
    except Exception as e:
        logging.error(f"Error in trivia command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def battle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a song battle - vote between two random songs."""
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    logging.info(f"Received /battle command from user {user_id}")
    
    try:
        songs = load_songs()
        if len(songs) < 2:
            await update.effective_message.reply_text("Need at least 2 songs for battles!")
            return
        
        # Filter out blacklisted songs
        filtered_songs = filter_blacklisted_songs(songs, user_id)
        if len(filtered_songs) < 2:
            await update.effective_message.reply_text("Not enough songs available for battle (some may be blacklisted).")
            return
        
        # Pick two random songs
        battle_songs = random.sample(filtered_songs, 2)
        song1, song2 = battle_songs
        
        # Create battle info
        battle_id = f"{chat_id}_{int(datetime.now().timestamp())}"
        
        # Create poll for battle
        song1_option = f"🎵 {song1.get('title')} — {song1.get('artist')}"
        song2_option = f"🎵 {song2.get('title')} — {song2.get('artist')}"
        
        question = "🥊 SONG BATTLE! Which song is better?"
        
        # Send battle description first
        battle_text = f"""🥊 **SONG BATTLE!**

**Fighter 1:** {song1.get('title')} — {song1.get('artist')}
🎵 Genre: {song1.get('genre')} | Year: {song1.get('year', 'Unknown')}
{song1.get('url', '')}

🆚

**Fighter 2:** {song2.get('title')} — {song2.get('artist')}
🎵 Genre: {song2.get('genre')} | Year: {song2.get('year', 'Unknown')}
{song2.get('url', '')}

Vote for your favorite! 👇"""
        
        await context.bot.send_message(chat_id=chat_id, text=battle_text, parse_mode='Markdown')
        
        # Send the battle poll
        poll = await context.bot.send_poll(
            chat_id=chat_id,
            question=question,
            options=[song1_option, song2_option],
            allows_multiple_answers=False,
            is_anonymous=False,
        )
        
        # Store battle context for tracking
        context.bot_data[f"battle_{poll.poll.id}"] = {
            "battle_id": battle_id,
            "song1": {
                "id": song1.get("id"),
                "title": song1.get("title"),
                "artist": song1.get("artist")
            },
            "song2": {
                "id": song2.get("id"), 
                "title": song2.get("title"),
                "artist": song2.get("artist")
            },
            "chat_id": chat_id,
            "start_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Error in battle command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def battle_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show battle statistics."""
    user_id = str(update.effective_user.id)
    logging.info(f"Received /battlestats command from user {user_id}")
    
    try:
        user_data = load_user_data()
        battles = user_data.get("battles", {})
        
        if not battles:
            await update.effective_message.reply_text("No battle data available yet! Start some battles with /battle")
            return
        
        songs = load_songs()
        song_dict = {str(song.get("id")): song for song in songs}
        
        # Calculate battle statistics
        song_wins = {}
        song_losses = {}
        total_battles = 0
        
        for battle_id, battle_data in battles.items():
            if "votes" not in battle_data:
                continue
                
            votes = battle_data["votes"]
            if not votes:
                continue
                
            # Count votes for each song
            song1_votes = sum(1 for vote in votes.values() if vote == 0)
            song2_votes = sum(1 for vote in votes.values() if vote == 1)
            
            if song1_votes == song2_votes:
                continue  # Skip ties
            
            winner_id = battle_data["song1"]["id"] if song1_votes > song2_votes else battle_data["song2"]["id"]
            loser_id = battle_data["song2"]["id"] if song1_votes > song2_votes else battle_data["song1"]["id"]
            
            winner_id = str(winner_id)
            loser_id = str(loser_id)
            
            song_wins[winner_id] = song_wins.get(winner_id, 0) + 1
            song_losses[loser_id] = song_losses.get(loser_id, 0) + 1
            total_battles += 1
        
        if total_battles == 0:
            await update.effective_message.reply_text("No completed battles yet! Vote in some battles to see stats.")
            return
        
        # Create leaderboard
        all_song_ids = set(song_wins.keys()) | set(song_losses.keys())
        song_records = []
        
        for song_id in all_song_ids:
            if song_id in song_dict:
                wins = song_wins.get(song_id, 0)
                losses = song_losses.get(song_id, 0)
                total = wins + losses
                win_rate = (wins / total * 100) if total > 0 else 0
                
                song_records.append({
                    "song": song_dict[song_id],
                    "wins": wins,
                    "losses": losses,
                    "win_rate": win_rate,
                    "total": total
                })
        
        # Sort by win rate, then by total battles
        song_records.sort(key=lambda x: (x["win_rate"], x["total"]), reverse=True)
        
        result_text = f"🥊 **BATTLE LEADERBOARD** ({total_battles} battles)\n\n"
        
        for i, record in enumerate(song_records[:10], 1):
            song = record["song"]
            wins = record["wins"]
            losses = record["losses"]
            win_rate = record["win_rate"]
            
            if i <= 3:
                medal = ["🥇", "🥈", "🥉"][i-1]
            else:
                medal = f"{i}."
            
            result_text += f"{medal} {song.get('title')} — {song.get('artist')}\n"
            result_text += f"   🏆 {wins}W-{losses}L ({win_rate:.1f}% win rate)\n\n"
        
        # User-specific stats
        user_votes = 0
        for battle_data in battles.values():
            if "votes" in battle_data and user_id in battle_data["votes"]:
                user_votes += 1
        
        result_text += f"📊 You've voted in {user_votes} battles"
        
        await update.effective_message.reply_text(result_text, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in battlestats command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def handle_battle_poll_answer(poll_answer, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle battle poll answers separately from rating polls."""
    poll_id = poll_answer.poll_id
    user_id = str(poll_answer.user.id)
    option_ids = poll_answer.option_ids
    
    if not option_ids:
        return
    
    battle_context = context.bot_data.get(f"battle_{poll_id}")
    if not battle_context:
        return  # Not a battle poll
    
    battle_id = battle_context["battle_id"]
    chosen_option = option_ids[0]  # 0 for song1, 1 for song2
    
    # Save the battle vote
    user_data = load_user_data()
    if "battles" not in user_data:
        user_data["battles"] = {}
    
    if battle_id not in user_data["battles"]:
        user_data["battles"][battle_id] = {
            "song1": battle_context["song1"],
            "song2": battle_context["song2"], 
            "start_time": battle_context["start_time"],
            "votes": {}
        }
    
    user_data["battles"][battle_id]["votes"][user_id] = chosen_option
    save_user_data(user_data)
    
    # Get winner info for logging
    winner_song = battle_context["song1"] if chosen_option == 0 else battle_context["song2"]
    logging.info(f"User {user_id} voted for {winner_song['title']} in battle {battle_id}")


async def add_song(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add new song (admin only)."""
    user_id = update.effective_user.id
    logging.info(f"Received /add command from user {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        await update.effective_message.reply_text("❌ Admin access required.")
        return
    
    try:
        args = context.args
        if len(args) < 2:
            await update.effective_message.reply_text("Usage: /add [title] [artist] [url] [genre] [year]")
            return
        
        songs = load_songs()
        new_id = max([song.get("id", 0) for song in songs], default=0) + 1
        
        title = args[0]
        artist = args[1]
        url = args[2] if len(args) > 2 else ""
        genre = args[3] if len(args) > 3 else "unknown"
        year = int(args[4]) if len(args) > 4 and args[4].isdigit() else None
        
        new_song = {
            "id": new_id,
            "title": title,
            "artist": artist,
            "url": url,
            "genre": genre
        }
        
        if year:
            new_song["year"] = year
        
        songs.append(new_song)
        
        with open(SONGS_FILE, "w", encoding="utf-8") as f:
            json.dump(songs, f, indent=2, ensure_ascii=False)
        
        await update.effective_message.reply_text(f"✅ Added: {title} — {artist}")
        
    except Exception as e:
        logging.error(f"Error in add command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def remove_song(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove song (admin only)."""
    user_id = update.effective_user.id
    logging.info(f"Received /remove command from user {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        await update.effective_message.reply_text("❌ Admin access required.")
        return
    
    try:
        args = context.args
        if not args or not args[0].isdigit():
            await update.effective_message.reply_text("Usage: /remove [song_id]")
            return
        
        song_id = int(args[0])
        songs = load_songs()
        
        song_to_remove = None
        for song in songs:
            if song.get("id") == song_id:
                song_to_remove = song
                break
        
        if not song_to_remove:
            await update.effective_message.reply_text(f"Song with ID {song_id} not found.")
            return
        
        songs.remove(song_to_remove)
        
        with open(SONGS_FILE, "w", encoding="utf-8") as f:
            json.dump(songs, f, indent=2, ensure_ascii=False)
        
        await update.effective_message.reply_text(f"✅ Removed: {song_to_remove.get('title')} — {song_to_remove.get('artist')}")
        
    except Exception as e:
        logging.error(f"Error in remove command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def reload_songs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reload song database (admin only)."""
    user_id = update.effective_user.id
    logging.info(f"Received /reload command from user {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        await update.effective_message.reply_text("❌ Admin access required.")
        return
    
    try:
        songs = load_songs()
        await update.effective_message.reply_text(f"✅ Reloaded {len(songs)} songs from database.")
        
    except Exception as e:
        logging.error(f"Error in reload command: {e}")
        await update.effective_message.reply_text("Sorry, an error occurred. Please try again later.")


async def send_rating_poll(context: ContextTypes.DEFAULT_TYPE, chat_id: int, song: Dict[str, Any]) -> None:
    """Send a rating poll for a song."""
    options = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    question = f"Rate: {song.get('title', 'Unknown Title')}"
    
    poll = await context.bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=options,
        allows_multiple_answers=False,
        is_anonymous=False,
    )
    
    # Store poll context for rating tracking
    context.bot_data[f"poll_{poll.poll.id}"] = {
        "song_id": song.get("id"),
        "song_title": song.get("title"),
        "chat_id": chat_id
    }


async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle poll answers for both song ratings and battles."""
    poll_answer = update.poll_answer
    poll_id = poll_answer.poll_id
    user_id = str(poll_answer.user.id)
    option_ids = poll_answer.option_ids
    
    if not option_ids:
        return
    
    # Check if it's a battle poll first
    battle_context = context.bot_data.get(f"battle_{poll_id}")
    if battle_context:
        await handle_battle_poll_answer(poll_answer, context)
        return
    
    # Handle rating poll
    poll_context = context.bot_data.get(f"poll_{poll_id}")
    if not poll_context:
        return
    
    song_id = str(poll_context["song_id"])
    rating = option_ids[0] + 1  # Convert 0-based index to 1-based rating
    
    # Save the rating
    user_data = load_user_data()
    if "ratings" not in user_data:
        user_data["ratings"] = {}
    
    if song_id not in user_data["ratings"]:
        user_data["ratings"][song_id] = {}
    
    user_data["ratings"][song_id][user_id] = rating
    save_user_data(user_data)
    
    logging.info(f"User {user_id} rated song {song_id} with {rating}/10")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    chat = update.effective_chat
    logging.info(f"Received /start command from user {update.effective_user.id} in {chat.type} chat {chat.id}")
    
    help_text = """🎵 **Pahari Music Bot** 🎵

**🎧 Discovery Commands:**
/recommend - Get today's song recommendation
/random - Get a completely random song
/discover - Personalized recommendations based on your ratings
/similar - Find songs similar to the last one

**🔍 Search & Filter:**
/genre [rock/metal/grunge] - Filter songs by genre
/artist [name] - Find songs by specific artist
/search [keyword] - Search song titles

**❤️ Personal Preferences:**
/favorite - Mark last song as favorite
/myfavorites - List your favorite songs
/blacklist - Manage songs you never want to hear
/myratings - Show your rating history

**📊 Statistics & Community:**
/stats - Show song ratings and popularity
/toprated - Show highest-rated songs

**🎮 Fun Features:**
/quote - Get a random music quote
/trivia - Music trivia quiz
/battle - Song vs song voting battles
/battlestats - Battle leaderboard and statistics

**🔧 Admin Commands:**
/add [title] [artist] [url] [genre] [year] - Add new song
/remove [song_id] - Remove song
/reload - Reload song database

Rate songs with polls to improve your recommendations! 🎶"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log all incoming messages for debugging."""
    user = update.effective_user
    message = update.message
    chat = update.effective_chat
    chat_type = chat.type
    
    logging.info(f"Received message from user {user.id} ({user.username}) in {chat_type} chat {chat.id}: '{message.text}'")
    
    # If it's a command that we don't handle, let them know
    if message.text and message.text.startswith('/'):
        await message.reply_text(f"Unknown command: {message.text}. Try /start for help or /recommend for today's song.")


def get_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable is not set."
        )
    return token


def build_app() -> Application:
    token = get_token()
    app = ApplicationBuilder().token(token).build()
    
    # Add command handlers with logging
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("recommend", recommend))
    app.add_handler(CommandHandler("random", random_song))
    app.add_handler(CommandHandler("genre", genre_filter))
    app.add_handler(CommandHandler("artist", artist_search))
    app.add_handler(CommandHandler("search", search_songs))
    app.add_handler(CommandHandler("favorite", favorite_song))
    app.add_handler(CommandHandler("myfavorites", my_favorites))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("toprated", top_rated))
    app.add_handler(CommandHandler("myratings", my_ratings))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("blacklist", blacklist_command))
    app.add_handler(CommandHandler("discover", discover_command))
    app.add_handler(CommandHandler("similar", similar_command))
    app.add_handler(CommandHandler("trivia", trivia_command))
    app.add_handler(CommandHandler("battle", battle_command))
    app.add_handler(CommandHandler("battlestats", battle_stats_command))
    app.add_handler(CommandHandler("add", add_song))
    app.add_handler(CommandHandler("remove", remove_song))
    app.add_handler(CommandHandler("reload", reload_songs))
    
    # Add poll answer handler for rating tracking
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    
    # Add a message handler to catch all messages for debugging
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logging.info("Registered all command handlers + poll answer handler + message handler")
    
    return app


def main() -> None:
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Load environment variables from .env file
    load_dotenv()
    
    try:
        app = build_app()
        logger.info("Bot started successfully. Press Ctrl+C to stop.")
        # Start polling (press Ctrl+C to stop)
        app.run_polling(close_loop=False)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    main()
