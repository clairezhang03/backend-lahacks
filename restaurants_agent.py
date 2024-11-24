from typing import List, Dict, Any
from fetchai.uagents import Agent, Context, Model
from fetchai.uagents.config import DEFAULT_ENDPOINTS
import requests
from supabase import create_client, Client
from pydantic import BaseModel
from datetime import datetime

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

class YelpRestaurantAgent(Agent):
    def __init__(self, name: str, yelp_api_key: str, supabase_url: str, supabase_key: str):
        super().__init__(name=name, endpoint=DEFAULT_ENDPOINTS["default"])
        
        # Initialize Yelp API settings
        self.api_key = yelp_api_key
        self.headers = {'Authorization': f'Bearer {self.api_key}'}
        self.yelp_base_url = 'https://api.yelp.com/v3/businesses'
        
        # Initialize Supabase
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Track seen restaurants to avoid duplicates
        self.seen_restaurants = set()

    async def clear_restaurants(self, ctx: Context):
        """Clear existing restaurants table"""
        try:
            self.supabase.table('restaurants').delete().execute()
            ctx.logger.info("Cleared existing restaurants")
        except Exception as e:
            ctx.logger.error(f"Error clearing restaurants: {str(e)}")

    async def search_restaurants(self, ctx: Context, location: str) -> List[Dict]:
        """Search for restaurants in a given location using Yelp API"""
        try:
            params = {
                'location': location,
                'categories': 'restaurants',
                'limit': 50,  # Maximum allowed by Yelp
                'sort_by': 'rating'
            }
            
            response = requests.get(
                f'{self.yelp_base_url}/search',
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json().get('businesses', [])
        except Exception as e:
            ctx.logger.error(f"Error searching restaurants: {str(e)}")
            return []

    def transform_to_restaurant(self, business: Dict) -> Dict:
        """Transform Yelp business data into our Restaurant model"""
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

    async def collect_restaurants(self, ctx: Context, location: str):
        """Collect restaurants for a specific location"""
        ctx.logger.info(f"Starting restaurant collection for {location}")
        
        # Get restaurants from Yelp
        restaurants = await self.search_restaurants(ctx, location)
        
        for business in restaurants:
            try:
                if business['id'] not in self.seen_restaurants:
                    self.seen_restaurants.add(business['id'])
                    
                    # Transform restaurant data
                    restaurant_data = self.transform_to_restaurant(business)
                    
                    # Store in Supabase
                    result = self.supabase.table('restaurants').upsert(
                        restaurant_data,
                        on_conflict='yelp_id'  # Assuming you have a unique constraint on yelp_id
                    ).execute()
                    
                    ctx.logger.info(f"Stored restaurant: {restaurant_data['name']}")
                    
            except Exception as e:
                ctx.logger.error(f"Error processing restaurant {business.get('name')}: {str(e)}")
        
        ctx.logger.info(f"Completed collecting restaurants for {location}")

    @Agent.on_interval(period=86400)  # Run daily
    async def scheduled_collection(self, ctx: Context):
        """Daily scheduled collection for predefined locations"""
        locations = [
            "Los Angeles, CA",
            "Santa Monica, CA",
            "Beverly Hills, CA",
            "Culver City, CA"
        ]
        
        for location in locations:
            await self.collect_restaurants(ctx, location)

# Testing script
async def test_agent(yelp_api_key: str, supabase_url: str, supabase_key: str):
    """Test the restaurant agent"""
    print("\nTesting Restaurant Agent...")
    
    try:
        # Create agent
        agent = YelpRestaurantAgent(
            "test_agent",
            yelp_api_key,
            supabase_url,
            supabase_key
        )
        
        # Test location
        test_location = "Santa Monica, CA"
        
        print("\nTesting Yelp API connection...")
        restaurants = await agent.search_restaurants(agent.context, test_location)
        if restaurants:
            print(f"✅ Successfully retrieved {len(restaurants)} restaurants")
        else:
            print("❌ Failed to retrieve restaurants")
            return
        
        print("\nTesting Supabase connection...")
        try:
            # Test query
            result = agent.supabase.table('restaurants').select("*").limit(1).execute()
            print("✅ Successfully connected to Supabase")
        except Exception as e:
            print(f"❌ Supabase connection failed: {str(e)}")
            return
        
        print("\nTesting data collection...")
        await agent.collect_restaurants(agent.context, test_location)
        
        # Verify data in Supabase
        result = agent.supabase.table('restaurants').select("*").execute()
        count = len(result.data)
        print(f"✅ Successfully stored {count} restaurants in Supabase")
        
        if count > 0:
            sample = result.data[0]
            print("\nSample restaurant data:")
            print(f"Name: {sample['name']}")
            print(f"Cuisine: {sample['main_cuisine']}")
            print(f"Rating: {sample['rating']}")
            print(f"Address: {sample['address']}")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")

# Example usage
if __name__ == "__main__":
    import asyncio
    
    # Your credentials
    YELP_API_KEY = "your_yelp_api_key_here"
    SUPABASE_URL = "your_supabase_url_here"
    SUPABASE_KEY = "your_supabase_key_here"
    
    # Run tests
    asyncio.run(test_agent(YELP_API_KEY, SUPABASE_URL, SUPABASE_KEY))