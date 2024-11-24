import requests
from typing import List, Dict, Any
from fetchai.uagents import Agent, Context, Model
from fetchai.uagents.config import DEFAULT_ENDPOINTS
import firebase_admin
from firebase_admin import credentials, firestore
from pydantic import BaseModel

# Data Models
class Restaurant(Model):
    name: str
    location: List[float]  # [latitude, longitude]
    address: str
    link: str = None
    cuisine: List[str] = []
    main_cuisine: str
    immutable_time: bool = True
    hours: Dict = None
    phone: str = None
    rating: float = None
    price: str = None
    image_url: str = None
    review_count: int = None
    transactions: List[str] = []

class YelpRestaurantAgent(Agent):
    def __init__(self, name: str, yelp_api_key: str, firebase_cred_path: str):
        super().__init__(name=name, endpoint=DEFAULT_ENDPOINTS["default"])
        
        # Initialize Yelp API settings
        self.api_key = yelp_api_key
        self.headers = {'Authorization': f'Bearer {self.api_key}'}
        self.yelp_base_url = 'https://api.yelp.com/v3/businesses'
        
        # Initialize Firebase
        cred = credentials.Certificate(firebase_cred_path)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()
        
        # Initialize collections
        self.restaurants_collection = self.db.collection('restaurants')
        
        # Track seen restaurants to avoid duplicates
        self.seen_restaurants = set()

    async def clear_collection(self, ctx: Context):
        """Clear existing restaurants collection"""
        try:
            docs = self.restaurants_collection.list_documents()
            for doc in docs:
                doc.delete()
            ctx.logger.info("Cleared existing restaurants collection")
        except Exception as e:
            ctx.logger.error(f"Error clearing collection: {str(e)}")

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

    def transform_to_restaurant(self, business: Dict) -> Restaurant:
        """Transform Yelp business data into our Restaurant model"""
        cuisines = [cat['title'] for cat in business.get('categories', [])]
        
        return Restaurant(
            name=business['name'].replace("/", " "),
            location=[
                business['coordinates']['latitude'],
                business['coordinates']['longitude']
            ],
            address=', '.join(business['location'].get('display_address', [])),
            link=business.get('url'),
            cuisine=cuisines,
            main_cuisine=cuisines[0] if cuisines else "Unknown",
            phone=business.get('phone'),
            rating=business.get('rating'),
            price=business.get('price'),
            image_url=business.get('image_url'),
            review_count=business.get('review_count'),
            transactions=business.get('transactions', []),
            hours=None  # Would require additional API call to get hours
        )

    async def collect_restaurants(self, ctx: Context, location: str):
        """Collect restaurants for a specific location"""
        ctx.logger.info(f"Starting restaurant collection for {location}")
        
        # Clear existing data
        await self.clear_collection(ctx)
        
        # Get restaurants from Yelp
        restaurants = await self.search_restaurants(ctx, location)
        
        for business in restaurants:
            try:
                if business['id'] not in self.seen_restaurants:
                    self.seen_restaurants.add(business['id'])
                    
                    # Transform and store restaurant data
                    restaurant = self.transform_to_restaurant(business)
                    
                    # Store in Firebase
                    self.restaurants_collection.document(restaurant.name).set(
                        restaurant.dict()
                    )
                    
                    ctx.logger.info(f"Stored restaurant: {restaurant.name}")
                    
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

# Example usage
if __name__ == "__main__":
    YELP_API_KEY = "your_yelp_api_key_here"
    FIREBASE_CRED_PATH = "path_to_your_firebase_credentials.json"
    
    # Create and start the agent
    agent = YelpRestaurantAgent(
        "restaurant_collector",
        YELP_API_KEY,
        FIREBASE_CRED_PATH
    )
    
    # Run the agent
    agent.run()