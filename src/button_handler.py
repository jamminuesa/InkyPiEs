import threading
import logging
import select
import time
import gpiod
import gpiodevice
from gpiod.line import Bias, Direction, Edge
from plugins.plugin_registry import get_plugin_instance
from PIL import Image

logger = logging.getLogger(__name__)

class ButtonHandler:
    """Manages physical buttons and delegates actions to active plugin"""
    
    # GPIO pins for buttons (BCM numbering)
    SW_A = 5
    SW_B = 6
    SW_C = 16  # Set to 25 for Impression 13.3"
    SW_D = 24
    
    BUTTONS = [SW_A, SW_B, SW_C, SW_D]
    LABELS = ["A", "B", "C", "D"]
    
    # Anti-bounce configuration
    DEBOUNCE_TIME = 0.3  # Seconds between presses of the same button
    
    def __init__(self, device_config, display_manager, refresh_task):
        self.device_config = device_config
        self.display_manager = display_manager
        self.refresh_task = refresh_task
        
        self.running = False
        self.thread = None
        
        # GPIO setup
        self.chip = None
        self.request = None
        self.offsets = None
        
        # Anti-bounce: timestamp of last press per button
        self.last_press_time = {}
        
        # Processing lock: prevents multiple simultaneous processing
        self.processing_lock = threading.Lock()
        self.is_processing = False
        
        logger.info("ButtonHandler initialized with anti-bounce protection")
    
    def start(self):
        """Starts the button listener in a separate thread"""
        if self.thread and self.thread.is_alive():
            logger.warning("ButtonHandler already running")
            return
        
        try:
            # Setup GPIO
            INPUT = gpiod.LineSettings(
                direction=Direction.INPUT,
                bias=Bias.PULL_UP,
                edge_detection=Edge.FALLING
            )
            
            self.chip = gpiodevice.find_chip_by_platform()
            self.offsets = [self.chip.line_offset_from_id(id) for id in self.BUTTONS]
            line_config = dict.fromkeys(self.offsets, INPUT)
            
            self.request = self.chip.request_lines(
                consumer="inkypi-buttons",
                config=line_config
            )
            
            logger.info("GPIO configured correctly for buttons")
            
            # Start reading thread
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            logger.info("ButtonHandler started and listening for events")
            
        except Exception as e:
            logger.error(f"Error starting ButtonHandler: {e}")
            self.running = False
    
    def stop(self):
        """Stops the button listener"""
        self.running = False
        
        if self.request:
            self.request.release()
            self.request = None
        
        if self.thread:
            self.thread.join(timeout=2)
        
        logger.info("ButtonHandler stopped")
    
    def _run(self):
        """
        Main loop that listens for button events
        Compatible version: uses select() with timeout
        """
        logger.info("Starting button reading loop (select mode)")
        
        while self.running:
            try:
                # Use select() to wait for events with timeout
                fd = self.request.fd
                
                # Wait up to 0.1 seconds for events
                readable, _, _ = select.select([fd], [], [], 0.1)
                
                if readable:
                    # Events available, read them
                    try:
                        events = self.request.read_edge_events()
                        for event in events:
                            self._handle_button_event(event)
                    except Exception as e:
                        logger.error(f"Error reading events: {e}")
                
            except Exception as e:
                if self.running:
                    logger.error(f"Error in button loop: {e}")
                    time.sleep(0.5)
                else:
                    break
        
        logger.info("Button loop finished")
    
    def _handle_button_event(self, event):
        """
        Handles a button event with anti-bounce protection
        This runs in the main button listener thread - must be fast!
        """
        try:
            # Identify which button was pressed
            index = self.offsets.index(event.line_offset)
            gpio_number = self.BUTTONS[index]
            label = self.LABELS[index]
            
            current_time = time.time()
            
            # PROTECTION 1: Debouncing per button
            last_time = self.last_press_time.get(label, 0)
            time_since_last_press = current_time - last_time
            
            if time_since_last_press < self.DEBOUNCE_TIME:
                logger.debug(f"Ignoring bounce of button {label} "
                           f"({time_since_last_press:.2f}s since last press)")
                return
            
            # Update timestamp of this press
            self.last_press_time[label] = current_time
            
            # PROTECTION 2: Global processing lock
            if self.is_processing:
                logger.warning(f"Button {label} pressed but processing already in progress. Ignoring.")
                return
            
            logger.info(f"Button pressed: {label} (GPIO {gpio_number})")
            
            # Mark that we're processing
            with self.processing_lock:
                self.is_processing = True
            
            # CRITICAL: Process button in a SEPARATE THREAD
            # This allows the main loop to continue detecting (and rejecting) button presses
            # while the image is being generated and displayed
            processing_thread = threading.Thread(
                target=self._process_button_async,
                args=(label,),
                daemon=True,
                name=f"ButtonProcess-{label}"
            )
            processing_thread.start()
            
        except Exception as e:
            logger.exception(f"Error handling button event: {e}")
            # Ensure we release the lock in case of error
            with self.processing_lock:
                self.is_processing = False
    
    def _process_button_async(self, label):
        """
        Processes button action asynchronously in a separate thread
        This is where the potentially slow operations happen
        """
        try:
            logger.debug(f"Processing button {label} in thread {threading.current_thread().name}")
            
            # Get active plugin info
            refresh_info = self.device_config.get_refresh_info()
            plugin_id = refresh_info.plugin_id if refresh_info else None
            
            if not plugin_id:
                logger.warning(f"Button {label} pressed but no active plugin")
                return
            
            # Get plugin instance
            plugin_config = self.device_config.get_plugin(plugin_id)
            if not plugin_config:
                logger.error(f"Plugin config {plugin_id} not found")
                return
            
            plugin = get_plugin_instance(plugin_config)
            
            # Check if plugin supports buttons
            if not hasattr(plugin, 'handle_button'):
                logger.debug(f"Plugin {plugin_id} doesn't support buttons")
                return
            
            # Call plugin's button handler
            logger.info(f"Delegating button {label} to plugin {plugin_id}")
            result = plugin.handle_button(label, self.device_config)
            
            # If plugin returns an image, update the display
            if isinstance(result, Image.Image):
                logger.info(f"Plugin returned new image, updating display")
                self.display_manager.display_image(
                    result,
                    image_settings=plugin.config.get("image_settings", [])
                )
                
                # Update image hash in refresh_info
                from utils.image_utils import compute_image_hash
                image_hash = compute_image_hash(result)
                refresh_info.image_hash = image_hash
                self.device_config.write_config()
                
                logger.info(f"Display updated after pressing button {label}")
            elif result is not None:
                logger.debug(f"Plugin returned: {result}")
            
        except Exception as e:
            logger.exception(f"Error processing button {label}: {e}")
        finally:
            # ALWAYS release the processing lock, even if there was an error
            with self.processing_lock:
                self.is_processing = False
                logger.debug(f"Button {label} processing completed, lock released")
    
    def simulate_button_press(self, button_label):
        """
        Simulates a button press (useful for testing or web UI)
        
        Args:
            button_label: 'A', 'B', 'C', or 'D'
        """
        if button_label not in self.LABELS:
            logger.error(f"Invalid button label: {button_label}")
            return
        
        logger.info(f"Simulating button press: {button_label}")
