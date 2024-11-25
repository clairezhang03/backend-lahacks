from uagents import Agent, Bureau, Context, Model
from datetime import datetime
import asyncio

# Import the models and agent from your main script
# Assuming the main script is named restaurant_agent.py
from restaurant_agent import LocationMessage, RestaurantMessage, restaurant_agent

# Create a test agent to interact with the restaurant agent
test_agent = Agent(
    name="test_agent",
    seed="test_agent recovery phrase"
)

# Track received responses
received_restaurants = []

@test_agent.on_message(model=RestaurantMessage)
async def handle_restaurant_response(ctx: Context, sender: str, msg: RestaurantMessage):
    """Handle the restaurant information received from the restaurant agent"""
    global received_restaurants
    received_restaurants = msg.restaurants
    
    ctx.logger.info(f"\n{'='*50}")
    ctx.logger.info(f"Received {len(msg.restaurants)} restaurants from {sender}")
    
    # Display sample of received data
    for i, restaurant in enumerate(msg.restaurants[:3], 1):
        ctx.logger.info(f"\nRestaurant {i}:")
        ctx.logger.info(f"Name: {restaurant.get('name')}")
        ctx.logger.info(f"Cuisine: {restaurant.get('main_cuisine')}")
        ctx.logger.info(f"Rating: {restaurant.get('rating')}")
        ctx.logger.info(f"Address: {restaurant.get('address')}")
    
    ctx.logger.info(f"\n{'='*50}")

@test_agent.on_interval(period=10.0)
async def run_test(ctx: Context):
    """Send a test location request every 10 seconds"""
    test_location = "Santa Monica, CA"
    ctx.logger.info(f"\nSending location request: {test_location}")
    
    # Send location request to restaurant agent
    await ctx.send(restaurant_agent.address, LocationMessage(location=test_location))

# Set up the bureau
bureau = Bureau()
bureau.add(restaurant_agent)
bureau.add(test_agent)

if __name__ == "__main__":
    print("\n=== Starting Restaurant Agent Test ===")
    print(f"Test started at: {datetime.now()}")
    print("\nWatching for restaurant data...")
    print("(Press Ctrl+C to stop)")
    
    try:
        bureau.run()
    except KeyboardInterrupt:
        print("\n\nTest stopped by user")
        if received_restaurants:
            print(f"Successfully received {len(received_restaurants)} restaurants")
        else:
            print("No restaurants were received")