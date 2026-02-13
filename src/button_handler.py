#!/usr/bin/env python3
"""
Button Handler for InkyPi
Manages physical buttons and delegates actions to active plugins
"""

import threading
import logging
import gpiod
import gpiodevice
from gpiod.line import Bias, Direction, Edge
from plugins.plugin_registry import get_plugin_instance
from PIL import Image

logger = logging.getLogger(__name__)

class ButtonHandler:
    """Gestiona los botones físicos y delega acciones al plugin activo"""
    
    # GPIO pins for buttons (BCM numbering)
    SW_A = 5
    SW_B = 6
    SW_C = 16  # Set to 25 for Impression 13.3"
    SW_D = 24
    
    BUTTONS = [SW_A, SW_B, SW_C, SW_D]
    LABELS = ["A", "B", "C", "D"]
    
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
        
        logger.info("ButtonHandler inicializado")
    
    def start(self):
        """Inicia el listener de botones en un hilo separado"""
        if self.thread and self.thread.is_alive():
            logger.warning("ButtonHandler ya está corriendo")
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
            
            logger.info("GPIO configurado correctamente para botones")
            
            # Iniciar hilo de lectura
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            logger.info("ButtonHandler iniciado y escuchando eventos")
            
        except Exception as e:
            logger.error(f"Error iniciando ButtonHandler: {e}")
            self.running = False
    
    def stop(self):
        """Detiene el listener de botones"""
        self.running = False
        
        if self.request:
            self.request.release()
            self.request = None
        
        if self.thread:
            self.thread.join(timeout=2)
        
        logger.info("ButtonHandler detenido")
    
    def _run(self):
        """Loop principal que escucha eventos de botones"""
        logger.info("Iniciando loop de lectura de botones")
        
        while self.running:
            try:
                # Leer eventos con timeout para permitir salida limpia
                for event in self.request.read_edge_events(timeout=0.1):
                    self._handle_button_event(event)
            except TimeoutError:
                # Timeout normal, continuar loop
                continue
            except Exception as e:
                logger.error(f"Error leyendo eventos de botones: {e}")
                if not self.running:
                    break
        
        logger.info("Loop de botones finalizado")
    
    def _handle_button_event(self, event):
        """Procesa un evento de botón"""
        try:
            # Identificar qué botón se presionó
            index = self.offsets.index(event.line_offset)
            gpio_number = self.BUTTONS[index]
            label = self.LABELS[index]
            
            logger.info(f"Botón presionado: {label} (GPIO {gpio_number})")
            
            # Obtener información del plugin activo
            refresh_info = self.device_config.get_refresh_info()
            plugin_id = refresh_info.plugin_id if refresh_info else None
            
            if not plugin_id:
                logger.warning(f"Botón {label} presionado pero no hay plugin activo")
                return
            
            # Obtener instancia del plugin
            plugin_config = self.device_config.get_plugin(plugin_id)
            if not plugin_config:
                logger.error(f"Configuración de plugin {plugin_id} no encontrada")
                return
            
            plugin = get_plugin_instance(plugin_config)
            
            # Verificar si el plugin soporta botones
            if not hasattr(plugin, 'handle_button'):
                logger.debug(f"Plugin {plugin_id} no soporta botones")
                return
            
            # Llamar al manejador de botones del plugin
            logger.info(f"Delegando botón {label} a plugin {plugin_id}")
            result = plugin.handle_button(label, self.device_config)
            
            # Si el plugin devuelve una imagen, actualizar el display
            if isinstance(result, Image.Image):
                logger.info(f"Plugin retornó nueva imagen, actualizando display")
                self.display_manager.display_image(
                    result,
                    image_settings=plugin.config.get("image_settings", [])
                )
                
                # Actualizar el hash de la imagen en refresh_info
                from utils.image_utils import compute_image_hash
                image_hash = compute_image_hash(result)
                refresh_info.image_hash = image_hash
                self.device_config.write_config()
                
                logger.info(f"Display actualizado tras presionar botón {label}")
            elif result is not None:
                logger.debug(f"Plugin retornó: {result}")
            
        except Exception as e:
            logger.exception(f"Error manejando evento de botón: {e}")
    
    def simulate_button_press(self, button_label):
        """
        Simula la pulsación de un botón (útil para testing o web UI)
        
        Args:
            button_label: 'A', 'B', 'C', o 'D'
        """
        if button_label not in self.LABELS:
            logger.error(f"Etiqueta de botón inválida: {button_label}")
            return
        
        logger.info(f"Simulando pulsación de botón {button_label}")
        
        # Crear un objeto event simulado
        class SimulatedEvent:
            def __init__(self, offset):
                self.line_offset = offset
        
        index = self.LABELS.index(button_label)
        offset = self.offsets[index] if self.offsets else index
        event = SimulatedEvent(offset)
        
        self._handle_button_event(event)
