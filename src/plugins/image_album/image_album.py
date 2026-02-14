import logging
from random import choice

from PIL import Image, ImageColor, ImageOps
from utils.http_client import get_http_session
from plugins.base_plugin.base_plugin import BasePlugin
from utils.image_utils import pad_image_blur

logger = logging.getLogger(__name__)


class ImmichProvider:
    def __init__(self, base_url: str, key: str, image_loader):
        self.base_url = base_url
        self.key = key
        self.headers = {"x-api-key": self.key}
        self.image_loader = image_loader
        self.session = get_http_session()

    def get_album_id(self, album: str) -> str:
        logger.debug(f"Fetching albums from {self.base_url}")
        r = self.session.get(f"{self.base_url}/api/albums", headers=self.headers)
        r.raise_for_status()
        albums = r.json()

        matching_albums = [a for a in albums if a["albumName"] == album]
        if not matching_albums:
            raise RuntimeError(f"Album '{album}' not found.")

        return matching_albums[0]["id"]

    def get_assets(self, album_id: str) -> list[dict]:
        """Fetch all assets from album."""
        all_items = []
        page_items = [1]
        page = 1

        logger.debug(f"Fetching assets from album {album_id}")
        while page_items:
            body = {
                "albumIds": [album_id],
                "size": 1000,
                "page": page
            }
            r2 = self.session.post(f"{self.base_url}/api/search/metadata", json=body, headers=self.headers)
            r2.raise_for_status()
            assets_data = r2.json()

            page_items = assets_data.get("assets", {}).get("items", [])
            all_items.extend(page_items)
            page += 1

        logger.debug(f"Found {len(all_items)} total assets in album")
        return all_items

    def get_image(self, album: str, dimensions: tuple[int, int], resize: bool = True) -> Image.Image | None:
        """
        Get a random image from the album.

        Args:
            album: Album name
            dimensions: Target dimensions (width, height)
            resize: Whether to let loader resize (False when padding will be applied)

        Returns:
            PIL Image or None on error
        """
        try:
            logger.info(f"Getting id for album '{album}'")
            album_id = self.get_album_id(album)
            logger.info(f"Getting assets from album id {album_id}")
            assets = self.get_assets(album_id)

            if not assets:
                logger.error(f"No assets found in album '{album}'")
                return None

        except Exception as e:
            logger.error(f"Error retrieving album data from {self.base_url}: {e}")
            return None

        # Select random asset
        selected_asset = choice(assets)
        asset_id = selected_asset["id"]
        asset_url = f"{self.base_url}/api/assets/{asset_id}/original"

        logger.info(f"Selected random asset: {asset_id}")
        logger.debug(f"Downloading from: {asset_url}")

        # Use adaptive image loader for memory-efficient processing
        # Let loader resize when requested (when no padding will be applied)
        img = self.image_loader.from_url(
            asset_url,
            dimensions,
            timeout_ms=40000,
            resize=resize,
            headers=self.headers
        )

        if not img:
            logger.error(f"Failed to load image {asset_id} from Immich")
            return None

        logger.info(f"Successfully loaded image: {img.size[0]}x{img.size[1]}")
        return img


class ImageAlbum(BasePlugin):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Caché de settings para usar en handle_button
        self.cached_settings = None
    
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['api_key'] = {
            "required": True,
            "service": "Immich",
            "expected_key": "IMMICH_KEY"
        }
        return template_params

    def generate_image(self, settings, device_config):
        logger.info("=== Image Album Plugin: Starting image generation ===")
        
        # Cachear settings para usar en handle_button
        self.cached_settings = settings

        orientation = device_config.get_config("orientation")
        dimensions = device_config.get_resolution()

        if orientation == "vertical":
            dimensions = dimensions[::-1]
            logger.debug(f"Vertical orientation detected, dimensions: {dimensions[0]}x{dimensions[1]}")

        img = None
        album_provider = settings.get("albumProvider")
        logger.info(f"Album provider: {album_provider}")

        # Check padding options to determine resize strategy
        use_padding = settings.get('padImage') == "true"
        background_option = settings.get('backgroundOption', 'blur')
        logger.debug(f"Settings: pad_image={use_padding}, background_option={background_option}")

        match album_provider:
            case "Immich":
                key = device_config.load_env_key("IMMICH_KEY")
                if not key:
                    logger.error("Immich API Key not configured")
                    raise RuntimeError("Immich API Key not configured.")

                url = settings.get('url')
                if not url:
                    logger.error("Immich URL not provided")
                    raise RuntimeError("Immich URL is required.")

                album = settings.get('album')
                if not album:
                    logger.error("Album name not provided")
                    raise RuntimeError("Album name is required.")

                logger.info(f"Immich URL: {url}")
                logger.info(f"Album: {album}")

                provider = ImmichProvider(url, key, self.image_loader)
                # Let loader resize when no padding needed, otherwise load full-size for padding
                img = provider.get_image(album, dimensions, resize=not use_padding)

                if not img:
                    logger.error("Failed to retrieve image from Immich")
                    raise RuntimeError("Failed to load image, please check logs.")
            case _:
                logger.error(f"Unknown album provider: {album_provider}")
                raise RuntimeError(f"Unsupported album provider: {album_provider}")

        if img is None:
            logger.error("Image is None after provider processing")
            raise RuntimeError("Failed to load image, please check logs.")

        # Apply padding if requested (image was loaded at full size)
        if use_padding:
            logger.debug(f"Applying padding with {background_option} background")
            if background_option == "blur":
                img = pad_image_blur(img, dimensions)
            else:
                background_color = ImageColor.getcolor(
                    settings.get('backgroundColor') or "white",
                    img.mode
                )
                img = ImageOps.pad(img, dimensions, color=background_color, method=Image.Resampling.LANCZOS)
        # else: loader already resized to fit with proper aspect ratio

        logger.info("=== Image Album Plugin: Image generation complete ===")
        return img

    def handle_button(self, button_name, device_config):
        """
        Manages buttons for Image Album:

        A: Generate a new/next image from album
        B,C,D: Not configured
        """
        logger.info(f"ImageAlbum manejando botón {button_name}")

        # SOLUCIÓN: Usar settings cacheados del último generate_image
        # Esto funciona porque generate_image siempre se llama antes de handle_button
        settings = self.cached_settings
        
        if not settings:
            logger.error("No hay settings cacheados. generate_image debe ejecutarse primero.")
            logger.info("Intentando obtener settings desde refresh_info...")
            
            # Fallback: intentar obtener desde refresh_info
            try:
                refresh_info = device_config.get_refresh_info()
                playlist_manager = device_config.get_playlist_manager()
                
                if hasattr(refresh_info, 'plugin_instance') and playlist_manager:
                    plugin_instance_name = refresh_info.plugin_instance
                    
                    if playlist_manager.active_playlist:
                        active_playlist = playlist_manager.get_playlist(playlist_manager.active_playlist)
                        
                        if active_playlist:
                            # Buscar la instancia del plugin en la playlist
                            for plugin_inst in active_playlist.plugins:
                                if plugin_inst.name == plugin_instance_name:
                                    settings = plugin_inst.settings
                                    logger.info(f"Settings recuperados desde playlist: {plugin_instance_name}")
                                    break
                
                if not settings:
                    logger.error("No se pudieron recuperar settings. Abortando.")
                    return None
                    
            except Exception as e:
                logger.error(f"Error recuperando settings: {e}")
                return None
        
        logger.debug(f"Settings: albumProvider={settings.get('albumProvider')}, album={settings.get('album')}")

        # Botón A: Nueva imagen aleatoria
        if button_name == 'A':
            logger.info("Botón A: Generando nueva imagen aleatoria")
            try:
                return self.generate_image(settings, device_config)
            except Exception as e:
                logger.error(f"Error generando nueva imagen: {e}")
                return None

        # Botones B, C, D: No configurados
        elif button_name in ['B', 'C', 'D']:
            logger.info(f"ImageAlbum button {button_name} pressed")
            logger.info("Button not assigned yet")

        return None
