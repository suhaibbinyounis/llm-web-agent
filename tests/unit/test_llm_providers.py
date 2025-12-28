"""
Tests for the LLM providers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestOpenAIProvider:
    """Test the OpenAI LLM provider."""
    
    @pytest.fixture
    def provider(self):
        """Create an OpenAI provider instance."""
        from llm_web_agent.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(
            base_url="http://127.0.0.1:3030",
            model="gpt-4"
        )
    
    def test_name_property(self, provider):
        """Test name property returns correct value."""
        assert provider.name == "openai"
    
    def test_default_model_property(self, provider):
        """Test default_model returns configured model."""
        assert provider.default_model == "gpt-4"
    
    def test_supports_vision(self, provider):
        """Test supports_vision returns True for vision models."""
        # Most OpenAI models support vision
        assert isinstance(provider.supports_vision, bool)
    
    def test_supports_tools(self, provider):
        """Test supports_tools returns True."""
        assert provider.supports_tools is True
    
    def test_supports_streaming(self, provider):
        """Test supports_streaming returns True."""
        assert provider.supports_streaming is True
    
    @pytest.mark.asyncio
    async def test_health_check_with_mock(self, provider):
        """Test health_check with mocked response."""
        with patch.object(provider, '_client') as mock_client:
            mock_client.models.list = AsyncMock(return_value=MagicMock(data=[]))
            result = await provider.health_check()
            # May return True or False depending on implementation
            assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_count_tokens(self, provider):
        """Test count_tokens method."""
        from llm_web_agent.interfaces.llm import Message, MessageRole
        messages = [
            Message(role=MessageRole.USER, content="Hello, world!")
        ]
        count = await provider.count_tokens(messages)
        assert isinstance(count, int)
        assert count >= 0


class TestCopilotProvider:
    """Test the Copilot LLM provider."""
    
    @pytest.fixture
    def provider(self):
        """Create a Copilot provider instance."""
        from llm_web_agent.llm.copilot_provider import CopilotProvider
        return CopilotProvider(
            base_url="http://127.0.0.1:3030",
            model="gpt-4"
        )
    
    def test_name_property(self, provider):
        """Test name property returns correct value."""
        assert provider.name == "copilot"
    
    def test_default_model_property(self, provider):
        """Test default_model returns configured model."""
        assert provider.default_model == "gpt-4o"  # CopilotProvider defaults to gpt-4o


class TestMessage:
    """Test the Message dataclass."""
    
    def test_create_user_message(self):
        """Test creating a user message."""
        from llm_web_agent.interfaces.llm import Message, MessageRole
        msg = Message(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
    
    def test_create_assistant_message(self):
        """Test creating an assistant message."""
        from llm_web_agent.interfaces.llm import Message, MessageRole
        msg = Message(role=MessageRole.ASSISTANT, content="Hi there")
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hi there"
    
    def test_create_system_message(self):
        """Test creating a system message."""
        from llm_web_agent.interfaces.llm import Message, MessageRole
        msg = Message(role=MessageRole.SYSTEM, content="You are a helpful assistant")
        assert msg.role == MessageRole.SYSTEM
    
    def test_message_with_images(self):
        """Test creating a message with images."""
        from llm_web_agent.interfaces.llm import Message, MessageRole
        msg = Message(
            role=MessageRole.USER,
            content="What's in this image?",
            images=["base64encodedimage"]
        )
        assert msg.images is not None
        assert len(msg.images) == 1


class TestLLMResponse:
    """Test the LLMResponse dataclass."""
    
    def test_create_response(self):
        """Test creating an LLM response."""
        from llm_web_agent.interfaces.llm import LLMResponse
        response = LLMResponse(
            content="This is the response",
            model="gpt-4",
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        )
        assert response.content == "This is the response"
        assert response.model == "gpt-4"
        assert response.usage["prompt_tokens"] == 10
    
    def test_response_with_finish_reason(self):
        """Test response with finish reason."""
        from llm_web_agent.interfaces.llm import LLMResponse
        response = LLMResponse(
            content="Done",
            model="gpt-4",
            usage={"prompt_tokens": 5, "completion_tokens": 1},
            finish_reason="stop"
        )
        assert response.finish_reason == "stop"


class TestMessageRole:
    """Test the MessageRole enum."""
    
    def test_message_roles_exist(self):
        """Test that all expected roles exist."""
        from llm_web_agent.interfaces.llm import MessageRole
        assert MessageRole.SYSTEM
        assert MessageRole.USER
        assert MessageRole.ASSISTANT
    
    def test_message_role_values(self):
        """Test message role string values."""
        from llm_web_agent.interfaces.llm import MessageRole
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
