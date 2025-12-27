"""
Form Handler - Smart form field analysis, filling, and validation.

This module provides:
1. FormFieldAnalyzer: Discovers form structure (fields, labels, types)
2. FormFiller: Fills fields using smart matching (by label, placeholder, name)
3. FormValidator: Detects validation errors after form interaction

Key Features:
- Matches instructions to specific fields (not just first match)
- Uses accessibility-first locators (getByLabel, getByPlaceholder)
- Detects and reports form validation errors
- Handles multi-field forms correctly
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from difflib import SequenceMatcher

if TYPE_CHECKING:
    from playwright.async_api import Page, Locator

logger = logging.getLogger(__name__)


@dataclass
class FormField:
    """Represents a single form field with its metadata."""
    
    # Identification
    selector: str
    field_type: str  # text, email, password, tel, number, textarea, select, checkbox, radio
    
    # Labels and identification text
    label_text: Optional[str] = None
    placeholder: Optional[str] = None
    name: Optional[str] = None
    id: Optional[str] = None
    aria_label: Optional[str] = None
    
    # State
    value: Optional[str] = None
    is_required: bool = False
    is_disabled: bool = False
    is_readonly: bool = False
    is_visible: bool = True
    
    # Validation
    has_error: bool = False
    error_message: Optional[str] = None
    
    # Position (for ordering)
    index: int = 0
    
    def get_best_identifier(self) -> str:
        """Return the best human-readable identifier for this field."""
        return (
            self.label_text or 
            self.placeholder or 
            self.aria_label or 
            self.name or 
            self.id or 
            f"field_{self.index}"
        )
    
    def matches(self, target: str) -> float:
        """
        Calculate how well this field matches a target description.
        Returns score 0.0-1.0.
        """
        target_lower = target.lower().strip()
        
        # Check each identifier
        scores = []
        
        for identifier in [self.label_text, self.placeholder, self.aria_label, self.name, self.id]:
            if identifier:
                id_lower = identifier.lower()
                
                # Exact match
                if id_lower == target_lower:
                    return 1.0
                
                # Contains match
                if target_lower in id_lower or id_lower in target_lower:
                    scores.append(0.8)
                
                # Fuzzy match
                ratio = SequenceMatcher(None, target_lower, id_lower).ratio()
                if ratio > 0.6:
                    scores.append(ratio)
                
                # Word overlap
                target_words = set(target_lower.split())
                id_words = set(id_lower.replace('-', ' ').replace('_', ' ').split())
                overlap = len(target_words & id_words)
                if overlap > 0:
                    scores.append(overlap / max(len(target_words), len(id_words)))
        
        return max(scores) if scores else 0.0


@dataclass
class FormContext:
    """Complete form context with all fields and metadata."""
    
    fields: List[FormField] = field(default_factory=list)
    form_selector: Optional[str] = None
    page_url: str = ""
    has_errors: bool = False
    error_messages: List[str] = field(default_factory=list)
    
    def get_field_by_name(self, name: str) -> Optional[FormField]:
        """Find field by name attribute."""
        for f in self.fields:
            if f.name and f.name.lower() == name.lower():
                return f
        return None
    
    def get_field_by_label(self, label: str) -> Optional[FormField]:
        """Find field by label text (fuzzy)."""
        best_match = None
        best_score = 0.5  # Minimum threshold
        
        for f in self.fields:
            score = f.matches(label)
            if score > best_score:
                best_score = score
                best_match = f
        
        return best_match
    
    def get_input_fields(self) -> List[FormField]:
        """Get all fillable input fields (not buttons/checkboxes)."""
        return [
            f for f in self.fields 
            if f.field_type in ('text', 'email', 'password', 'tel', 'number', 'textarea', 'search', 'url')
        ]


class FormFieldAnalyzer:
    """
    Analyzes page to discover form structure.
    
    Extracts:
    - All input elements within forms or the page
    - Associated labels (via for=, aria-labelledby, wrapping <label>)
    - Placeholders, names, IDs
    - Field types and states
    """
    
    async def analyze(self, page: "Page") -> FormContext:
        """
        Analyze all form fields on the page.
        
        Returns FormContext with all discovered fields.
        """
        context = FormContext(page_url=page.url)
        
        # JavaScript to extract all form field information
        fields_data = await page.evaluate("""
            () => {
                const fields = [];
                
                // Find all input, textarea, select elements
                const inputs = document.querySelectorAll('input, textarea, select');
                
                inputs.forEach((el, index) => {
                    // Skip hidden, submit, button, image, file inputs
                    const type = el.tagName.toLowerCase() === 'input' 
                        ? (el.type || 'text').toLowerCase()
                        : el.tagName.toLowerCase();
                    
                    if (['hidden', 'submit', 'button', 'image', 'file', 'reset'].includes(type)) {
                        return;
                    }
                    
                    // Get label text
                    let labelText = null;
                    
                    // 1. Check for associated label via 'for' attribute
                    if (el.id) {
                        const label = document.querySelector(`label[for="${el.id}"]`);
                        if (label) {
                            labelText = label.textContent.trim();
                        }
                    }
                    
                    // 2. Check for wrapping label
                    if (!labelText) {
                        const parentLabel = el.closest('label');
                        if (parentLabel) {
                            // Get text excluding the input itself
                            const clone = parentLabel.cloneNode(true);
                            const inputClone = clone.querySelector('input, textarea, select');
                            if (inputClone) inputClone.remove();
                            labelText = clone.textContent.trim();
                        }
                    }
                    
                    // 3. Check aria-labelledby
                    if (!labelText && el.getAttribute('aria-labelledby')) {
                        const labelEl = document.getElementById(el.getAttribute('aria-labelledby'));
                        if (labelEl) {
                            labelText = labelEl.textContent.trim();
                        }
                    }
                    
                    // Get unique selector
                    let selector = '';
                    if (el.id) {
                        selector = `#${el.id}`;
                    } else if (el.name) {
                        selector = `[name="${el.name}"]`;
                    } else {
                        // Generate nth-of-type selector
                        const tag = el.tagName.toLowerCase();
                        const siblings = Array.from(el.parentElement?.children || []).filter(
                            c => c.tagName.toLowerCase() === tag
                        );
                        const nth = siblings.indexOf(el) + 1;
                        selector = `${tag}:nth-of-type(${nth})`;
                    }
                    
                    // Check for error state
                    const hasError = el.classList.contains('error') || 
                                    el.classList.contains('invalid') ||
                                    el.getAttribute('aria-invalid') === 'true' ||
                                    el.matches(':invalid');
                    
                    // Find associated error message
                    let errorMessage = null;
                    if (hasError) {
                        // Look for error message near the field
                        const parent = el.closest('.form-group, .field, .input-group') || el.parentElement;
                        const errorEl = parent?.querySelector('.error, .error-message, [role="alert"]');
                        if (errorEl) {
                            errorMessage = errorEl.textContent.trim();
                        }
                    }
                    
                    fields.push({
                        selector: selector,
                        field_type: type === 'textarea' ? 'textarea' : 
                                   type === 'select' ? 'select' : type,
                        label_text: labelText,
                        placeholder: el.placeholder || null,
                        name: el.name || null,
                        id: el.id || null,
                        aria_label: el.getAttribute('aria-label') || null,
                        value: el.value || null,
                        is_required: el.required || el.getAttribute('aria-required') === 'true',
                        is_disabled: el.disabled,
                        is_readonly: el.readOnly,
                        is_visible: el.offsetParent !== null,
                        has_error: hasError,
                        error_message: errorMessage,
                        index: index
                    });
                });
                
                return fields;
            }
        """)
        
        # Convert to FormField objects
        for data in fields_data:
            context.fields.append(FormField(**data))
        
        # Check for any form-level errors
        context.has_errors = any(f.has_error for f in context.fields)
        context.error_messages = [
            f.error_message for f in context.fields 
            if f.error_message
        ]
        
        logger.info(f"Analyzed form: {len(context.fields)} fields found")
        return context


class FormFiller:
    """
    Smart form filler that matches fields by label/placeholder/name.
    
    Ensures each field is filled exactly once with correct value.
    """
    
    def __init__(self, page: "Page"):
        self.page = page
        self.analyzer = FormFieldAnalyzer()
    
    async def fill_fields(
        self, 
        field_values: Dict[str, str],
        clear_first: bool = True
    ) -> List[Tuple[str, bool, Optional[str]]]:
        """
        Fill multiple fields with smart matching.
        
        Args:
            field_values: Dict mapping field identifiers to values
                         e.g., {"first name": "John", "last name": "Doe"}
            clear_first: Whether to clear fields before filling
            
        Returns:
            List of (field_name, success, error) tuples
        """
        results = []
        
        # Analyze form
        context = await self.analyzer.analyze(self.page)
        
        if not context.fields:
            logger.warning("No form fields found on page")
            return [(name, False, "No form fields found") for name in field_values]
        
        # Match and fill each field
        for target, value in field_values.items():
            success, error = await self._fill_single_field(context, target, value, clear_first)
            results.append((target, success, error))
        
        return results
    
    async def _fill_single_field(
        self,
        context: FormContext,
        target: str,
        value: str,
        clear_first: bool
    ) -> Tuple[bool, Optional[str]]:
        """Fill a single field using smart matching."""
        
        # Find best matching field
        field = context.get_field_by_label(target)
        
        if not field:
            # Try by name
            field = context.get_field_by_name(target)
        
        if not field:
            # Try matching against all fields
            best_match = None
            best_score = 0.5
            
            for f in context.get_input_fields():
                score = f.matches(target)
                if score > best_score:
                    best_score = score
                    best_match = f
            
            field = best_match
        
        if not field:
            error = f"Could not find field matching '{target}'"
            logger.warning(error)
            return False, error
        
        if not field.is_visible:
            error = f"Field '{target}' is not visible"
            logger.warning(error)
            return False, error
        
        if field.is_disabled or field.is_readonly:
            error = f"Field '{target}' is disabled or readonly"
            logger.warning(error)
            return False, error
        
        try:
            # Use the most specific locator available
            locator = await self._get_best_locator(field)
            
            if clear_first:
                await locator.clear()
            
            await locator.fill(value)
            
            logger.info(f"Filled '{field.get_best_identifier()}' with value")
            return True, None
            
        except Exception as e:
            error = f"Failed to fill '{target}': {e}"
            logger.error(error)
            return False, error
    
    async def _get_best_locator(self, field: FormField) -> "Locator":
        """Get the best Playwright locator for a field."""
        
        # Priority order:
        # 1. getByLabel (accessibility-first)
        # 2. getByPlaceholder
        # 3. ID selector
        # 4. Name selector
        # 5. Original selector
        
        if field.label_text:
            try:
                locator = self.page.get_by_label(field.label_text, exact=False)
                if await locator.count() == 1:
                    return locator
            except:
                pass
        
        if field.placeholder:
            try:
                locator = self.page.get_by_placeholder(field.placeholder, exact=False)
                if await locator.count() == 1:
                    return locator
            except:
                pass
        
        if field.id:
            return self.page.locator(f"#{field.id}")
        
        if field.name:
            return self.page.locator(f"[name='{field.name}']")
        
        return self.page.locator(field.selector)
    
    async def fill_by_label(self, label: str, value: str) -> bool:
        """Fill a field by its label text."""
        try:
            # Try Playwright's accessibility locator first
            locator = self.page.get_by_label(label, exact=False)
            if await locator.count() == 1:
                await locator.fill(value)
                return True
            
            # Fall back to smart matching
            results = await self.fill_fields({label: value})
            return results[0][1] if results else False
            
        except Exception as e:
            logger.error(f"Failed to fill by label '{label}': {e}")
            return False


class FormValidator:
    """
    Detects form validation errors after interaction.
    
    Checks:
    - Field-level errors (aria-invalid, :invalid, .error class)
    - Form-level error messages
    - Alert/toast messages
    """
    
    def __init__(self, page: "Page"):
        self.page = page
    
    async def check_errors(self) -> Tuple[bool, List[str]]:
        """
        Check for form validation errors.
        
        Returns:
            (has_errors, list_of_error_messages)
        """
        errors = await self.page.evaluate("""
            () => {
                const errors = [];
                
                // Check for invalid fields
                const invalidFields = document.querySelectorAll(
                    '[aria-invalid="true"], :invalid, .error, .invalid, .is-invalid'
                );
                
                invalidFields.forEach(el => {
                    // Skip if it's a form or fieldset
                    if (['FORM', 'FIELDSET'].includes(el.tagName)) return;
                    
                    // Get associated error message
                    const parent = el.closest('.form-group, .field, .input-group') || el.parentElement;
                    const errorEl = parent?.querySelector('.error-message, .help-block.error, [role="alert"], .invalid-feedback');
                    
                    if (errorEl) {
                        errors.push(errorEl.textContent.trim());
                    } else if (el.validationMessage) {
                        errors.push(el.validationMessage);
                    }
                });
                
                // Check for global error messages
                const globalErrors = document.querySelectorAll(
                    '.alert-error, .alert-danger, .error-summary, [role="alert"]:not(input):not(textarea)'
                );
                
                globalErrors.forEach(el => {
                    const text = el.textContent.trim();
                    if (text && !errors.includes(text)) {
                        errors.push(text);
                    }
                });
                
                // Check for toast/notification errors
                const toasts = document.querySelectorAll('.toast.error, .notification.error, .snackbar.error');
                toasts.forEach(el => {
                    const text = el.textContent.trim();
                    if (text && !errors.includes(text)) {
                        errors.push(text);
                    }
                });
                
                return errors;
            }
        """)
        
        has_errors = len(errors) > 0
        
        if has_errors:
            logger.warning(f"Form errors detected: {errors}")
        
        return has_errors, errors
    
    async def wait_for_validation(self, timeout_ms: int = 2000) -> Tuple[bool, List[str]]:
        """
        Wait for validation to complete, then check errors.
        
        Some forms validate async, so we wait briefly and recheck.
        """
        await asyncio.sleep(0.5)  # Initial wait for JS validation
        
        has_errors, errors = await self.check_errors()
        
        if not has_errors:
            # Wait a bit more for async validation
            await asyncio.sleep(0.3)
            has_errors, errors = await self.check_errors()
        
        return has_errors, errors


# Convenience function for integration
async def analyze_form(page: "Page") -> FormContext:
    """Analyze form fields on a page."""
    analyzer = FormFieldAnalyzer()
    return await analyzer.analyze(page)


async def fill_form(page: "Page", field_values: Dict[str, str]) -> List[Tuple[str, bool, Optional[str]]]:
    """Fill form fields with smart matching."""
    filler = FormFiller(page)
    return await filler.fill_fields(field_values)


async def check_form_errors(page: "Page") -> Tuple[bool, List[str]]:
    """Check for form validation errors."""
    validator = FormValidator(page)
    return await validator.check_errors()
