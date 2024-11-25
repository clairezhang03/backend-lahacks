import json
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

# Initialize Supabase client at module level
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Restaurant(Model):
    name: str
    location: List[float]
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
    location: str
    user_id: str

class RestaurantMessage(Model):
    restaurants: List[Dict]
    user_id: str

restaurant_agent = Agent(
    name="restaurant_agent",
    seed="restaurant_agent recovery phrase",
)

@restaurant_agent.on_message(model=LocationMessage)
async def handle_location_request(ctx: Context, sender: str, msg: LocationMessage):
    """Handle incoming location requests and respond with restaurant information"""
    ctx.logger.info(f"Received location request from {sender} for user {msg.user_id}: {msg.location}")
    
    restaurants = await search_restaurants(ctx, msg.location)
    if restaurants:
        try:
            # Transform restaurants data
            transformed_restaurants = [transform_to_restaurant(restaurant) for restaurant in restaurants]

            # Prepare update data
            trip_update = {
                'restaurants_found': True,
                'restaurants': transformed_restaurants
            }

            # Update and properly handle response
            response = supabase.table('Trips').update(
                trip_update
            ).eq('id', msg.user_id).execute()

        except Exception as e:
            ctx.logger.error(f"Update error: {str(e)}")
            import traceback
            ctx.logger.error(f"Traceback: {traceback.format_exc()}")
    else:
        ctx.logger.error(f"No restaurants found for location: {msg.location}")

async def search_restaurants(ctx: Context, location: str) -> List[Dict]:
    """Search for restaurants using Yelp API"""
    headers = {'Authorization': f'Bearer {YELP_API_KEY}'}
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
        "yelp_id": business.get('id'),  # Make sure to include the yelp_id
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

bureau = Bureau()
bureau.add(restaurant_agent)

if __name__ == "__main__":
    bureau.run()