"""
Stable Diffusion Adapter.

This adapter handles communication with Stable Diffusion WebUI/A1111 API
and similar SD-based image generation services.

SD WebUI API: https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API
"""

import base64
import json
from typing import Any, AsyncIterator, Dict, Set

import httpx

from app.gateway.adapters.base import (
    AdapterBase,
    AdapterError,
    RouteContext,
    UpstreamRequest,
)


class StableDiffusionAdapter(AdapterBase):
    """
    Adapter for Stable Diffusion WebUI/A1111 API.

    Translates OpenAI image generation requests to SD WebUI format.

    OpenAI format:
    {
        "model": "dall-e-3",
        "prompt": "a white siamese cat",
        "n": 1,
        "size": "1024x1024",
        "quality": "standard",
        "response_format": "b64_json"
    }

    SD WebUI format (txt2img):
    {
        "prompt": "a white siamese cat",
        "negative_prompt": "",
        "steps": 20,
        "width": 1024,
        "height": 1024,
        "batch_size": 1,
        "sampler_name": "DPM++ 2M Karras"
    }
    """

    ADAPTER_TYPE = "stable_diffusion"

    SUPPORTED_CAPABILITIES: Set[str] = {
        "images_generations",
        "images_edits",
        "images_variations",
    }

    # SD WebUI endpoints
    TXT2IMG_PATH = "/sdapi/v1/txt2img"
    IMG2IMG_PATH = "/sdapi/v1/img2img"

    # Default generation parameters
    DEFAULT_STEPS = 20
    DEFAULT_CFG_SCALE = 7
    DEFAULT_SAMPLER = "DPM++ 2M Karras"

    # Size mapping (OpenAI sizes to width/height)
    SIZE_MAP = {
        "256x256": (256, 256),
        "512x512": (512, 512),
        "1024x1024": (1024, 1024),
        "1024x1792": (1024, 1792),
        "1792x1024": (1792, 1024),
    }

    async def build_upstream_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Build request for Stable Diffusion WebUI."""

        endpoint = route_ctx.endpoint

        if "generations" in endpoint:
            return await self._build_txt2img_request(openai_request, route_ctx)
        elif "edits" in endpoint or "variations" in endpoint:
            return await self._build_img2img_request(openai_request, route_ctx)
        else:
            raise AdapterError(
                message=f"Unsupported endpoint for Stable Diffusion: {endpoint}",
                error_type="invalid_request_error",
                status_code=400
            )

    async def _build_txt2img_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Build txt2img request."""

        base_url = route_ctx.upstream_base_url.rstrip("/")
        url = f"{base_url}{self.TXT2IMG_PATH}"

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # SD WebUI may require authentication
        if route_ctx.upstream_auth_type == "bearer" and route_ctx.upstream_credentials:
            headers["Authorization"] = f"Bearer {route_ctx.upstream_credentials}"
        elif route_ctx.upstream_auth_type == "header" and route_ctx.upstream_credentials:
            try:
                header_name, header_value = route_ctx.upstream_credentials.split(":", 1)
                headers[header_name.strip()] = header_value.strip()
            except ValueError:
                pass

        headers.update(route_ctx.inject_headers)

        # Parse size
        size_str = openai_request.get("size", "1024x1024")
        width, height = self.SIZE_MAP.get(size_str, (1024, 1024))

        # Build SD request body
        body = {
            "prompt": openai_request.get("prompt", ""),
            "negative_prompt": openai_request.get("negative_prompt", ""),
            "steps": openai_request.get("steps", self.DEFAULT_STEPS),
            "cfg_scale": openai_request.get("cfg_scale", self.DEFAULT_CFG_SCALE),
            "width": width,
            "height": height,
            "batch_size": openai_request.get("n", 1),
            "sampler_name": openai_request.get("sampler", self.DEFAULT_SAMPLER),
        }

        # Quality mapping (OpenAI "hd" -> higher steps)
        quality = openai_request.get("quality", "standard")
        if quality == "hd":
            body["steps"] = max(body["steps"], 30)
            body["cfg_scale"] = max(body["cfg_scale"], 8)

        # Model override (SD checkpoint)
        if route_ctx.model_override:
            body["override_settings"] = {"sd_model_checkpoint": route_ctx.model_override}
        elif route_ctx.upstream_model:
            body["override_settings"] = {"sd_model_checkpoint": route_ctx.upstream_model}

        # Seed for reproducibility
        if "seed" in openai_request:
            body["seed"] = openai_request["seed"]
        else:
            body["seed"] = -1  # Random

        return UpstreamRequest(
            method="POST",
            url=url,
            headers=headers,
            body=body,
            stream=False
        )

    async def _build_img2img_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Build img2img request for edits/variations."""

        base_url = route_ctx.upstream_base_url.rstrip("/")
        url = f"{base_url}{self.IMG2IMG_PATH}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if route_ctx.upstream_auth_type == "bearer" and route_ctx.upstream_credentials:
            headers["Authorization"] = f"Bearer {route_ctx.upstream_credentials}"

        headers.update(route_ctx.inject_headers)

        # Parse size
        size_str = openai_request.get("size", "1024x1024")
        width, height = self.SIZE_MAP.get(size_str, (1024, 1024))

        # Get input image (should be base64)
        input_image = openai_request.get("image", "")
        if input_image.startswith("data:"):
            # Remove data URL prefix
            input_image = input_image.split(",", 1)[-1]

        body = {
            "init_images": [input_image],
            "prompt": openai_request.get("prompt", ""),
            "negative_prompt": openai_request.get("negative_prompt", ""),
            "steps": openai_request.get("steps", self.DEFAULT_STEPS),
            "cfg_scale": openai_request.get("cfg_scale", self.DEFAULT_CFG_SCALE),
            "width": width,
            "height": height,
            "batch_size": openai_request.get("n", 1),
            "sampler_name": openai_request.get("sampler", self.DEFAULT_SAMPLER),
            "denoising_strength": openai_request.get("denoising_strength", 0.75),
        }

        # Mask for inpainting (edits endpoint)
        if "mask" in openai_request:
            mask = openai_request["mask"]
            if mask.startswith("data:"):
                mask = mask.split(",", 1)[-1]
            body["mask"] = mask
            body["inpainting_fill"] = 1  # Fill masked area

        return UpstreamRequest(
            method="POST",
            url=url,
            headers=headers,
            body=body,
            stream=False
        )

    async def parse_upstream_response(
        self,
        upstream_response: httpx.Response,
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """Parse Stable Diffusion WebUI response."""

        if upstream_response.status_code >= 400:
            try:
                error_body = upstream_response.json()
            except Exception:
                error_body = {"error": upstream_response.text}

            raise AdapterError(
                message=error_body.get("error", "Unknown SD error"),
                error_type="api_error",
                status_code=upstream_response.status_code,
                upstream_response=upstream_response
            )

        try:
            sd_response = upstream_response.json()
        except Exception as e:
            raise AdapterError(
                message=f"Failed to parse SD response: {e}",
                error_type="parse_error",
                status_code=502
            )

        return self._transform_response(sd_response, route_ctx)

    def _transform_response(
        self,
        sd_response: Dict[str, Any],
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """
        Transform SD response to OpenAI format.

        SD format:
        {
            "images": ["base64_encoded_image1", "base64_encoded_image2"],
            "parameters": {...},
            "info": "{\"seed\": 12345, ...}"
        }

        OpenAI format:
        {
            "created": 1234567890,
            "data": [
                {"b64_json": "base64_encoded_image1"},
                {"b64_json": "base64_encoded_image2"}
            ]
        }
        """
        import time

        images = sd_response.get("images", [])

        # Parse generation info
        info = {}
        info_str = sd_response.get("info", "{}")
        try:
            info = json.loads(info_str) if isinstance(info_str, str) else info_str
        except json.JSONDecodeError:
            pass

        data = []
        for i, image_b64 in enumerate(images):
            item = {
                "b64_json": image_b64,
            }

            # Add revised prompt if available
            if info.get("prompt"):
                item["revised_prompt"] = info.get("prompt")

            data.append(item)

        return {
            "created": int(time.time()),
            "data": data,
            "model": route_ctx.virtual_model,
        }

    async def stream_translate(
        self,
        upstream_stream: AsyncIterator[bytes],
        route_ctx: RouteContext
    ) -> AsyncIterator[str]:
        """SD image generation doesn't support streaming."""
        raise AdapterError(
            message="Streaming not supported for image generation",
            error_type="invalid_request_error",
            status_code=400
        )
        yield ""
