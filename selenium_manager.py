import threading
import queue
import time
import os
import random
import math
from datetime import datetime
from typing import Callable, Any, Optional, Dict
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Task:
    """Represents a task to be executed by the browser"""
    
    def __init__(self, func: Callable, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.exception = None
        self.completed = threading.Event()
        self.task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    def execute(self, driver):
        """Execute the task with the given driver"""
        try:
            logger.info(f"Executing task: {self.task_id}")
            self.result = self.func(driver, *self.args, **self.kwargs)
            logger.info(f"Task {self.task_id} completed successfully")
        except Exception as e:
            self.exception = e
            logger.error(f"Task {self.task_id} failed: {str(e)}")
        finally:
            self.completed.set()
    
    def wait_for_completion(self, timeout=None):
        """Wait for task completion and return result"""
        if self.completed.wait(timeout):
            if self.exception:
                raise self.exception
            return self.result
        else:
            raise TimeoutError(f"Task {self.task_id} timed out")

class SeleniumManager:
    """Singleton Selenium Browser Manager with Queue System"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SeleniumManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.driver = None
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        self.setup_lock = threading.Lock()
        
        # Configuration
        self.max_retry_attempts = 3
        self.default_wait_time = 20
        self.page_load_wait = 5
        
        logger.info("SeleniumManager initialized")
    
    def _setup_driver(self):
        """Setup Chrome driver with optimal settings"""
        try:
            logger.info("Setting up ChromeDriver...")
            
            # Try multiple approaches to get the right ChromeDriver
            approaches = [
                self._setup_uc_chrome_manual,
                self._setup_uc_chrome_auto,
                self._setup_uc_chrome_headless
            ]
            
            for approach in approaches:
                try:
                    if approach():
                        logger.info("ChromeDriver setup completed successfully")
                        return True
                except Exception as e:
                    logger.warning(f"Approach failed: {str(e)}")
                    continue
            
            logger.error("All ChromeDriver setup approaches failed")
            return False
            
        except Exception as e:
            logger.error(f"Failed to setup ChromeDriver: {str(e)}")
            return False
    
    def _setup_uc_chrome_auto(self):
        """Try automatic undetected Chrome setup"""
        logger.info("Trying automatic undetected Chrome setup...")
        
        # Create fresh options for each attempt
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-default-apps")
        options.add_argument("--window-size=480,480")
        
        self.driver = uc.Chrome(options=options, version_main=None)
        # Set window size programmatically
        self.driver.set_window_size(480, 480)
        return True
    
    def _setup_uc_chrome_manual(self):
        """Try manual Chrome version detection"""
        logger.info("Trying manual Chrome version detection...")
        
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--window-size=480,480")
        
        # Try with specific Chrome version
        self.driver = uc.Chrome(options=options, version_main=136)
        # Set window size programmatically
        self.driver.set_window_size(480, 480)
        return True
    
    def _setup_uc_chrome_headless(self):
        """Try headless Chrome as last resort"""
        logger.info("Trying headless Chrome setup...")
        
        options = uc.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=480,480")
        
        self.driver = uc.Chrome(options=options)
        # Set window size programmatically (even in headless mode)
        self.driver.set_window_size(480, 480)
        return True
    
    def _worker_thread_func(self):
        """Worker thread function to process tasks sequentially"""
        logger.info("Worker thread started")
        
        while self.running:
            try:
                # Get task from queue with timeout
                task = self.task_queue.get(timeout=1)
                
                if task is None:  # Poison pill to stop worker
                    break
                
                # Ensure driver is available
                if not self.driver:
                    if not self._setup_driver():
                        task.exception = Exception("Failed to setup driver")
                        task.completed.set()
                        continue
                
                # Execute task
                task.execute(self.driver)
                
                # Mark task as done
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker thread error: {str(e)}")
                continue
        
        logger.info("Worker thread stopped")
    
    def start(self):
        """Start the browser manager"""
        with self.setup_lock:
            if self.running:
                logger.warning("SeleniumManager is already running")
                return
            
            logger.info("Starting SeleniumManager...")
            self.running = True
            
            # Start worker thread
            self.worker_thread = threading.Thread(target=self._worker_thread_func, daemon=True)
            self.worker_thread.start()
            
            logger.info("SeleniumManager started successfully")
    
    def stop(self):
        """Stop the browser manager and cleanup"""
        with self.setup_lock:
            if not self.running:
                logger.warning("SeleniumManager is not running")
                return
            
            logger.info("Stopping SeleniumManager...")
            self.running = False
            
            # Add poison pill to stop worker thread
            self.task_queue.put(None)
            
            # Wait for worker thread to finish
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=5)
            
            # Close driver
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("Browser closed successfully")
                except Exception as e:
                    logger.error(f"Error closing browser: {str(e)}")
                finally:
                    self.driver = None
            
            logger.info("SeleniumManager stopped")
    
    def add_task(self, func: Callable, *args, **kwargs) -> Task:
        """Add a task to the execution queue"""
        if not self.running:
            raise RuntimeError("SeleniumManager is not running. Call start() first.")
        
        task = Task(func, *args, **kwargs)
        self.task_queue.put(task)
        logger.info(f"Task {task.task_id} added to queue")
        return task
    
    def execute_task(self, func: Callable, *args, timeout=300, **kwargs) -> Any:
        """Execute a task and wait for result"""
        task = self.add_task(func, *args, **kwargs)
        return task.wait_for_completion(timeout)
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.task_queue.qsize()
    
    def is_running(self) -> bool:
        """Check if manager is running"""
        return self.running
    
    def _human_like_delay(self, min_delay=0.1, max_delay=0.5):
        """Generate human-like delays between actions"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def _generate_bezier_curve(self, start_x, start_y, end_x, end_y, num_points=10):
        """Generate points along a bezier curve for natural mouse movement"""
        # Create control points for curve
        ctrl1_x = start_x + random.randint(-50, 50)
        ctrl1_y = start_y + random.randint(-50, 50)
        ctrl2_x = end_x + random.randint(-50, 50)
        ctrl2_y = end_y + random.randint(-50, 50)
        
        points = []
        for i in range(num_points):
            t = i / (num_points - 1)
            # Bezier curve formula
            x = (1-t)**3 * start_x + 3*(1-t)**2*t * ctrl1_x + 3*(1-t)*t**2 * ctrl2_x + t**3 * end_x
            y = (1-t)**3 * start_y + 3*(1-t)**2*t * ctrl1_y + 3*(1-t)*t**2 * ctrl2_y + t**3 * end_y
            points.append((int(x), int(y)))
        
        return points
    
    def simulate_human_mouse_movement(self, driver):
        """Simulate natural human mouse movements"""
        try:
            actions = ActionChains(driver)
            
            # Get window size
            window_size = driver.get_window_size()
            max_x = min(window_size['width'] - 50, 430)  # Leave margin and respect 480px window
            max_y = min(window_size['height'] - 50, 430)
            
            # Random starting position
            start_x = random.randint(50, max_x)
            start_y = random.randint(50, max_y)
            
            # Perform 3-5 random movements
            num_movements = random.randint(3, 5)
            
            for _ in range(num_movements):
                # Random end position
                end_x = random.randint(50, max_x)
                end_y = random.randint(50, max_y)
                
                # Generate curved path
                curve_points = self._generate_bezier_curve(start_x, start_y, end_x, end_y, 8)
                
                # Move along curve
                for point in curve_points:
                    actions.move_by_offset(point[0] - start_x, point[1] - start_y)
                    start_x, start_y = point
                    self._human_like_delay(0.05, 0.15)
                
                # Random action at destination
                action_choice = random.randint(1, 4)
                if action_choice == 1:
                    # Small pause
                    self._human_like_delay(0.2, 0.8)
                elif action_choice == 2:
                    # Random scroll
                    scroll_delta = random.randint(-300, 300)
                    driver.execute_script(f"window.scrollBy(0, {scroll_delta});")
                elif action_choice == 3:
                    # Small mouse circle
                    for angle in range(0, 360, 45):
                        radius = random.randint(5, 15)
                        offset_x = int(radius * math.cos(math.radians(angle)))
                        offset_y = int(radius * math.sin(math.radians(angle)))
                        actions.move_by_offset(offset_x, offset_y)
                        actions.perform()
                        self._human_like_delay(0.03, 0.08)
                        actions = ActionChains(driver)  # Reset actions
                
                # Update start position for next movement
                start_x, start_y = end_x, end_y
                
                # Random delay between movements
                self._human_like_delay(0.3, 1.2)
            
            logger.info("Human-like mouse movement simulation completed")
            
        except Exception as e:
            logger.error(f"Error during mouse simulation: {str(e)}")
    
    def simulate_random_user_activity(self, driver, duration_seconds=10):
        """Simulate random user activity for specified duration"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < duration_seconds:
                activity_type = random.randint(1, 4)
                
                if activity_type == 1:
                    # Mouse movements
                    self.simulate_human_mouse_movement(driver)
                elif activity_type == 2:
                    # Random scrolling
                    scroll_amount = random.randint(-500, 500)
                    driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                elif activity_type == 3:
                    # Page interaction simulation
                    try:
                        # Find random clickable element (but don't actually click)
                        elements = driver.find_elements(By.TAG_NAME, "div")
                        if elements:
                            random_element = random.choice(elements[:10])  # Only consider first 10
                            actions = ActionChains(driver)
                            actions.move_to_element(random_element)
                            actions.perform()
                    except:
                        pass
                elif activity_type == 4:
                    # Just wait (simulate reading)
                    self._human_like_delay(1.0, 3.0)
                
                # Random delay between activities
                self._human_like_delay(0.5, 2.0)
            
            logger.info(f"User activity simulation completed ({duration_seconds}s)")
            
        except Exception as e:
            logger.error(f"Error during user activity simulation: {str(e)}")
    
    def add_anti_detection_task(self, duration=15):
        """Add a task to simulate user activity for anti-detection"""
        return self.add_task(self.simulate_random_user_activity, duration_seconds=duration)
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()