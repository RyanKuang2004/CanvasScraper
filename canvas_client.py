import aiohttp
from config import Config
from datetime import datetime
import asyncio

class CanvasClient:
    def __init__(self):
        """Initialize the Canvas API client with configuration."""
        self.api_url = Config.CANVAS_URL
        self.api_token = Config.CANVAS_API_TOKEN
        self.headers = {'Authorization': f'Bearer {self.api_token}'}

    async def _get(self, session, endpoint):
        """Make a GET request to the Canvas API.
        
        Args:
            session (aiohttp.ClientSession): The active client session
            endpoint (str): The API endpoint to request
            
        Returns:
            dict: The JSON response data if successful, None if 404, raises Exception for other errors
        """
        url = f"{self.api_url}{endpoint}"
        async with session.get(url, headers=self.headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 404:
                print(f"Resource not found: {endpoint}")
                return None
            else:
                raise Exception(f"Failed to fetch {endpoint}: {response.status}")
            
    async def get_active_courses(self):
        """Retrieve all active courses for the authenticated user.
        
        Returns:
            list: A list of dictionaries containing course information
        """
        async with aiohttp.ClientSession() as session:
            courses = await self._get(session, "/courses")
            return [
                {"id": course["id"], "name": course["name"]} 
                for course in courses
                if course.get("enrollments") and 
                course["enrollments"][0].get("enrollment_state") == "active"
            ]

    async def get_modules(self, session, course_id):
        """Retrieve all modules for a course.
        
        Args:
            session (aiohttp.ClientSession): The active client session
            course_id (int): The Canvas course ID
            
        Returns:
            list: A list of module dictionaries
        """
        return await self._get(session, f"/courses/{course_id}/modules")

    async def get_module_items(self, session, course_id, module_id):
        """Retrieve all items within a module.
        
        Args:
            session (aiohttp.ClientSession): The active client session
            course_id (int): The Canvas course ID
            module_id (int): The Canvas module ID
            
        Returns:
            list: A list of module item dictionaries
        """
        return await self._get(session, f"/courses/{course_id}/modules/{module_id}/items")

    async def get_page_content(self, session, course_id, page_url):
        """Retrieve the content of a course page.
        
        Args:
            session (aiohttp.ClientSession): The active client session
            course_id (int): The Canvas course ID
            page_url (str): The page URL identifier
            
        Returns:
            str: The page content if successful, None otherwise
        """
        page = await self._get(session, f"/courses/{course_id}/pages/{page_url}")
        return page.get("body") if page else None

    async def get_quiz_content(self, session, course_id, quiz_id):
        """Retrieve the content of a quiz.
        
        Args:
            session (aiohttp.ClientSession): The active client session
            course_id (int): The Canvas course ID
            quiz_id (int): The Canvas quiz ID
            
        Returns:
            str: The quiz description if successful, None otherwise
        """
        quiz = await self._get(session, f"/courses/{course_id}/quizzes/{quiz_id}")
        return quiz.get("description") if quiz else None

    async def get_file_content(self, session, file_id):
        """Retrieve the content of a file.
        
        Args:
            session (aiohttp.ClientSession): The active client session
            file_id (int): The Canvas file ID
            
        Returns:
            str: The file content if successful, None otherwise
        """
        file_info = await self._get(session, f"/files/{file_id}")
        if file_info and (download_url := file_info.get("url")):
            async with session.get(download_url) as response:
                if response.status == 200:
                    return await response.text()
        return None

    async def fetch_module_item_content(self, session, course_id, module_item):
        """Fetch the content of a module item based on its type.
        
        Args:
            session (aiohttp.ClientSession): The active client session
            course_id (int): The Canvas course ID
            module_item (dict): The module item information
            
        Returns:
            str: The content of the module item if available, None otherwise
        """
        item_type = module_item.get("type")
        content_map = {
            "Page": lambda: self.get_page_content(session, course_id, module_item.get("page_url")),
            "File": lambda: self.get_file_content(session, module_item.get("content_id"))
        }
        
        # Ensure the content_map always returns an awaitable coroutine
        coroutine = content_map.get(item_type, lambda: asyncio.sleep(0))()
        return await coroutine

    async def get_due_dates(self, session, course_id):
        """Retrieve upcoming assignments and quizzes for a course.
        
        Args:
            session (aiohttp.ClientSession): The active client session
            course_id (int): The Canvas course ID
            
        Returns:
            list: Combined list of upcoming assignment and quiz information
        """
        current_date = datetime.now().date()

        def is_upcoming(due_at):
            if not due_at:
                return False
            try:
                # Parse ISO 8601 date string
                due_date = datetime.fromisoformat(due_at).date()
                return due_date >= current_date
            except ValueError:
                return False

        # Get assignments
        assignments = await self._get(session, f"/courses/{course_id}/assignments")
        assignment_data = []
        if assignments:
            assignment_data = [
                {'name': a['name'], 'due_at': a.get('due_at'), 'type': 'assignment'} 
                for a in assignments
                if is_upcoming(a.get('due_at'))
            ]

        # Get quizzes
        quizzes = await self._get(session, f"/courses/{course_id}/quizzes")
        quiz_data = []
        if quizzes:
            quiz_data = [
                {'name': q['title'], 'due_at': q.get('due_at'), 'type': 'quiz'} 
                for q in quizzes
                if is_upcoming(q.get('due_at'))
            ]

        return assignment_data + quiz_data

def main():
    """Main function to run the Canvas client and fetch data."""
    client = CanvasClient()
    
    async def run():
        async with aiohttp.ClientSession() as session:
            courses = await client.get_active_courses()
            print("Active Courses:", courses)
            
            for course in courses:
                modules = await client.get_modules(session, course['id'])
                print(f"Modules for {course['name']}:", modules)
                
                for module in modules:
                    items = await client.get_module_items(session, course['id'], module['id'])
                    print(f"Items in Module {module['name']}:", items)
                    
                    for item in items:
                        content = await client.fetch_module_item_content(session, course['id'], item)
                        print(f"Content for {item['title']}: {content[:100]}...")  # Print first 100 chars

                due_dates = await client.get_due_dates(session, course['id'])
                print(f"Upcoming Due Dates for {course['name']}:", due_dates)

    asyncio.run(run())

if __name__ == "__main__":
    main()