from uagents import Agent, Bureau, Context, Model
from typing import List, Dict, Any
import aiohttp
from supabase import create_client, Client
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get environment variables
YELP_API_KEY = os.getenv('YELP_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Data Models
class Restaurant(Model):
    name: str
    location: List[float]  # [latitude, longitude]
    address: str
    link: str = None
    cuisine: List[str] = []
    main_cuisine: str
    hours: Dict = None
    phone: str = None
    rating: float = None
    price: str = None
    image_url: str = None
    review_count: int = None
    transactions: List[str] = []
    created_at: str = datetime.now().isoformat()
    updated_at: str = datetime.now().isoformat()

class LocationMessage(Model):
    """Message model for requesting restaurants in a location"""
    location: str
    user_id: str  # Added user_id field

class RestaurantMessage(Model):
    """Message model for responding with restaurant information"""
    restaurants: List[Dict]
    user_id: str  # Added user_id field

# Initialize the agent
restaurant_agent = Agent(
    name="restaurant_agent",
    seed="restaurant_agent recovery phrase",
)

# Store API credentials as agent attributes
restaurant_agent.yelp_api_key = YELP_API_KEY
restaurant_agent.supabase_url = SUPABASE_URL 
restaurant_agent.supabase_key = SUPABASE_KEY
restaurant_agent.seen_restaurants = set()

# Initialize Supabase client
restaurant_agent.supabase = create_client(
    restaurant_agent.supabase_url,
    restaurant_agent.supabase_key
)

@restaurant_agent.on_message(model=LocationMessage)
async def handle_location_request(ctx: Context, sender: str, msg: LocationMessage):
    """Handle incoming location requests and respond with restaurant information"""
    ctx.logger.info(f"Received location request from {sender} for user {msg.user_id}: {msg.location}")
    
    restaurants = await search_restaurants(ctx, msg.location)
    if restaurants:
        # Update user's restaurants_found status and store restaurants data
        try:
            # Update the users table
            restaurant_agent.supabase.table('users').update({
                'restaurants_found': True,
                'restaurants': restaurants
            }).eq('id', msg.user_id).execute()
            
            ctx.logger.info(f"Updated user {msg.user_id} with restaurant data")
            
            # Also store individual restaurants in the restaurants table
            await store_restaurants(ctx, restaurants)
            
            # Send response back
            await ctx.send(sender, RestaurantMessage(
                restaurants=restaurants,
                user_id=msg.user_id
            ))
        except Exception as e:
            ctx.logger.error(f"Error updating user data: {str(e)}")
    else:
        ctx.logger.error(f"No restaurants found for location: {msg.location}")

async def search_restaurants(ctx: Context, location: str) -> List[Dict]:
    """Search for restaurants using Yelp API"""
    headers = {'Authorization': f'Bearer {restaurant_agent.yelp_api_key}'}
    params = {
        'location': location,
        'categories': 'restaurants',
        'limit': 30,
        'sort_by': 'rating'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.yelp.com/v3/businesses/search',
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('businesses', [])
                else:
                    ctx.logger.error(f"Yelp API error: {response.status}")
                    return []
    except Exception as e:
        ctx.logger.error(f"Error searching restaurants: {str(e)}")
        return []

def transform_to_restaurant(business: Dict) -> Dict:
    """Transform Yelp business data into Restaurant model format"""
    cuisines = [cat['title'] for cat in business.get('categories', [])]
    
    return {
        "name": business['name'].replace("/", " "),
        "location": [
            business['coordinates']['latitude'],
            business['coordinates']['longitude']
        ],
        "address": ', '.join(business['location'].get('display_address', [])),
        "link": business.get('url'),
        "cuisine": cuisines,
        "main_cuisine": cuisines[0] if cuisines else "Unknown",
        "phone": business.get('phone'),
        "rating": business.get('rating'),
        "price": business.get('price'),
        "image_url": business.get('image_url'),
        "review_count": business.get('review_count'),
        "transactions": business.get('transactions', []),
        "yelp_id": business.get('id'),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

async def store_restaurants(ctx: Context, restaurants: List[Dict]):
    """Store restaurants in Supabase database"""
    for business in restaurants:
        try:
            if business['id'] not in restaurant_agent.seen_restaurants:
                restaurant_agent.seen_restaurants.add(business['id'])
                restaurant_data = transform_to_restaurant(business)
                
                result = restaurant_agent.supabase.table('restaurants').upsert(
                    restaurant_data,
                    on_conflict='yelp_id'
                ).execute()
                
                ctx.logger.info(f"Stored restaurant: {restaurant_data['name']}")
                
        except Exception as e:
            ctx.logger.error(f"Error storing restaurant {business.get('name')}: {str(e)}")

# Bureau setup for running the agent
bureau = Bureau()
bureau.add(restaurant_agent)

if __name__ == "__main__":
    bureau.run()