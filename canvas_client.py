import aiohttp
from config import Config
from datetime import datetime
import asyncio
import logging
from typing import Dict, List, Optional, Union, Any
from contextlib import asynccontextmanager

class CanvasClientError(Exception):
    """Base exception for Canvas client errors."""
    pass


class CanvasAPIError(CanvasClientError):
    """Exception raised for Canvas API errors."""
    def __init__(self, message: str, status_code: int, endpoint: str):
        super().__init__(message)
        self.status_code = status_code
        self.endpoint = endpoint


class CanvasClient:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the Canvas API client with configuration.
        
        Args:
            session: Optional aiohttp session. If None, client will manage its own session.
        """
        self.api_url = Config.CANVAS_URL
        self.api_token = Config.CANVAS_API_TOKEN
        self.headers = {'Authorization': f'Bearer {self.api_token}'}
        self._session = session
        self._should_close_session = session is None
        self.logger = logging.getLogger(__name__)
        
        # Validate configuration
        if not self.api_url or not self.api_token:
            raise CanvasClientError("Canvas API URL and token must be configured")

    @asynccontextmanager
    async def _get_session(self):
        """Get or create an aiohttp session."""
        if self._session:
            yield self._session
        else:
            async with aiohttp.ClientSession() as session:
                yield session
    
    async def _get(self, session: aiohttp.ClientSession, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make a GET request to the Canvas API.
        
        Args:
            session: The active client session
            endpoint: The API endpoint to request
            
        Returns:
            The JSON response data if successful, None if 404
            
        Raises:
            CanvasAPIError: For API errors other than 404
        """
        url = f"{self.api_url}{endpoint}"
        self.logger.debug(f"Making GET request to: {url}")
        
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.debug(f"Successfully fetched {endpoint}")
                    return data
                elif response.status == 404:
                    self.logger.info(f"Resource not found: {endpoint}")
                    return None
                else:
                    error_msg = f"Failed to fetch {endpoint}: {response.status}"
                    self.logger.error(error_msg)
                    raise CanvasAPIError(error_msg, response.status, endpoint)
        except aiohttp.ClientError as e:
            error_msg = f"Network error fetching {endpoint}: {str(e)}"
            self.logger.error(error_msg)
            raise CanvasAPIError(error_msg, 0, endpoint)
            
    async def get_active_courses(self) -> List[Dict[str, Union[int, str]]]:
        """Retrieve all active courses for the authenticated user.
        
        Returns:
            A list of dictionaries containing course information
        """
        async with self._get_session() as session:
            courses = await self._get(session, "/courses")
            if not courses:
                return []
            
            return [
                {"id": course["id"], "name": course["name"]} 
                for course in courses
                if course.get("enrollments") and 
                course["enrollments"][0].get("enrollment_state") == "active"
            ]

    async def get_modules(self, session: aiohttp.ClientSession, course_id: int) -> Optional[List[Dict[str, Any]]]:
        """Retrieve all modules for a course.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            
        Returns:
            A list of module dictionaries or None if not found
        """
        return await self._get(session, f"/courses/{course_id}/modules")

    async def get_module_items(self, session: aiohttp.ClientSession, course_id: int, module_id: int) -> Optional[List[Dict[str, Any]]]:
        """Retrieve all items within a module.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            module_id: The Canvas module ID
            
        Returns:
            A list of module item dictionaries or None if not found
        """
        return await self._get(session, f"/courses/{course_id}/modules/{module_id}/items")

    async def get_page_content(self, session: aiohttp.ClientSession, course_id: int, page_url: str) -> Optional[str]:
        """Retrieve the content of a course page.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            page_url: The page URL identifier
            
        Returns:
            The page content if successful, None otherwise
        """
        page = await self._get(session, f"/courses/{course_id}/pages/{page_url}")
        return page.get("body") if page else None

    async def get_quiz_content(self, session: aiohttp.ClientSession, course_id: int, quiz_id: int) -> Optional[str]:
        """Retrieve the content of a quiz.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            quiz_id: The Canvas quiz ID
            
        Returns:
            The quiz description if successful, None otherwise
        """
        quiz = await self._get(session, f"/courses/{course_id}/quizzes/{quiz_id}")
        return quiz.get("description") if quiz else None

    async def get_file_content(self, session: aiohttp.ClientSession, file_id: int) -> Optional[str]:
        """Retrieve the content of a file.
        
        Args:
            session: The active client session
            file_id: The Canvas file ID
            
        Returns:
            The file content if successful, None otherwise
        """
        file_info = await self._get(session, f"/files/{file_id}")
        if file_info and (download_url := file_info.get("url")):
            try:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        self.logger.debug(f"Successfully retrieved file content for file {file_id}")
                        return content
                    else:
                        self.logger.warning(f"Failed to download file {file_id}: {response.status}")
            except aiohttp.ClientError as e:
                self.logger.error(f"Network error downloading file {file_id}: {str(e)}")
        return None

    async def fetch_module_item_content(self, session: aiohttp.ClientSession, course_id: int, module_item: Dict[str, Any]) -> Optional[str]:
        """Fetch the content of a module item based on its type.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            module_item: The module item information
            
        Returns:
            The content of the module item if available, None otherwise
        """
        item_type = module_item.get("type")
        
        if item_type == "Page":
            page_url = module_item.get("page_url")
            if page_url:
                return await self.get_page_content(session, course_id, page_url)
        elif item_type == "File":
            content_id = module_item.get("content_id")
            if content_id:
                return await self.get_file_content(session, content_id)
        
        self.logger.debug(f"Unsupported or missing content for item type: {item_type}")
        return None

    async def get_due_dates(self, session: aiohttp.ClientSession, course_id: int) -> List[Dict[str, Union[str, None]]]:
        """Retrieve upcoming assignments and quizzes for a course.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            
        Returns:
            Combined list of upcoming assignment and quiz information
        """
        current_date = datetime.now().date()

        def is_upcoming(due_at: Optional[str]) -> bool:
            """Check if a due date is upcoming."""
            if not due_at:
                return False
            try:
                # Parse ISO 8601 date string
                due_date = datetime.fromisoformat(due_at.replace('Z', '+00:00')).date()
                return due_date >= current_date
            except (ValueError, AttributeError) as e:
                self.logger.warning(f"Invalid date format: {due_at}, error: {e}")
                return False

        # Get assignments
        assignments = await self._get(session, f"/courses/{course_id}/assignments")
        assignment_data: List[Dict[str, Union[str, None]]] = []
        if assignments:
            assignment_data = [
                {'name': a['name'], 'due_at': a.get('due_at'), 'type': 'assignment'} 
                for a in assignments
                if is_upcoming(a.get('due_at'))
            ]

        # Get quizzes
        quizzes = await self._get(session, f"/courses/{course_id}/quizzes")
        quiz_data: List[Dict[str, Union[str, None]]] = []
        if quizzes:
            quiz_data = [
                {'name': q['title'], 'due_at': q.get('due_at'), 'type': 'quiz'} 
                for q in quizzes
                if is_upcoming(q.get('due_at'))
            ]

        return assignment_data + quiz_data

def main() -> None:
    """Main function to run the Canvas client and fetch data."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    client = CanvasClient()
    
    async def run() -> None:
        """Run the Canvas data fetching process."""
        async with aiohttp.ClientSession() as session:
            try:
                courses = await client.get_active_courses()
                print("Active Courses:", courses)
                
                for course in courses:
                    course_id = course['id']
                    course_name = course['name']
                    
                    modules = await client.get_modules(session, course_id)
                    if modules:
                        print(f"Modules for {course_name}:", modules)
                        
                        for module in modules:
                            module_id = module['id']
                            module_name = module['name']
                            
                            items = await client.get_module_items(session, course_id, module_id)
                            if items:
                                print(f"Items in Module {module_name}:", items)
                                
                                for item in items:
                                    content = await client.fetch_module_item_content(session, course_id, item)
                                    if content:
                                        print(f"Content for {item['title']}: {content[:100]}...")  # Print first 100 chars

                    due_dates = await client.get_due_dates(session, course_id)
                    if due_dates:
                        print(f"Upcoming Due Dates for {course_name}:", due_dates)
                        
            except CanvasClientError as e:
                print(f"Canvas client error: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")
                raise

    asyncio.run(run())

if __name__ == "__main__":
    main()