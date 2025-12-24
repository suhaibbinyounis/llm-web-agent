"""
Framework Hints - Pattern library for common UI frameworks.

Provides selector hints and detection patterns for:
- Material UI (MUI)
- Ant Design
- Chakra UI
- React-Select
- Bootstrap
- Tailwind UI / Headless UI

This helps when standard resolution fails by providing
framework-specific selector patterns.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class FrameworkPattern:
    """Pattern for detecting framework elements."""
    class_pattern: Optional[str] = None
    role: Optional[str] = None
    aria_pattern: Optional[Dict[str, str]] = None
    selector_hints: List[str] = None
    parent_hints: List[str] = None
    
    def __post_init__(self):
        if self.selector_hints is None:
            self.selector_hints = []
        if self.parent_hints is None:
            self.parent_hints = []


# Framework detection patterns
FRAMEWORK_SIGNATURES = {
    'mui': [
        r'Mui[A-Z]',
        r'MuiTypography',
        r'MuiButton',
        r'css-[a-z0-9]+-MuiBox',
    ],
    'ant_design': [
        r'ant-[a-z]+',
        r'anticon',
    ],
    'chakra': [
        r'chakra-[a-z]+',
        r'css-[a-z0-9]+.*chakra',
    ],
    'react_select': [
        r'react-select',
        r'__control$',
        r'__menu$',
    ],
    'bootstrap': [
        r'^btn-',
        r'^form-control',
        r'^nav-',
        r'^dropdown',
    ],
    'headless_ui': [
        r'headlessui',
        r'\[data-headlessui-state\]',
    ],
    'radix': [
        r'radix-',
        r'\[data-radix-',
    ],
}


# Component patterns by framework
FRAMEWORK_COMPONENTS: Dict[str, Dict[str, FrameworkPattern]] = {
    'mui': {
        'button': FrameworkPattern(
            class_pattern=r'Mui.*Button',
            selector_hints=[
                '.MuiButton-root',
                '.MuiIconButton-root',
                'button.MuiButtonBase-root',
            ],
        ),
        'input': FrameworkPattern(
            class_pattern=r'MuiInput|MuiTextField|MuiOutlinedInput',
            selector_hints=[
                '.MuiInputBase-input',
                '.MuiOutlinedInput-input',
                'input.MuiInputBase-input',
            ],
        ),
        'select': FrameworkPattern(
            class_pattern=r'MuiSelect',
            role='combobox',
            selector_hints=[
                '.MuiSelect-select',
                '[role="combobox"]',
            ],
        ),
        'menu_item': FrameworkPattern(
            class_pattern=r'MuiMenuItem',
            role='menuitem',
            selector_hints=[
                '.MuiMenuItem-root',
                '[role="menuitem"]',
                '.MuiMenu-list li',
            ],
        ),
        'option': FrameworkPattern(
            role='option',
            selector_hints=[
                '[role="option"]',
                '.MuiAutocomplete-option',
            ],
        ),
        'tab': FrameworkPattern(
            class_pattern=r'MuiTab',
            role='tab',
            selector_hints=[
                '.MuiTab-root',
                '[role="tab"]',
            ],
        ),
        'checkbox': FrameworkPattern(
            class_pattern=r'MuiCheckbox',
            role='checkbox',
            selector_hints=[
                '.MuiCheckbox-root input',
                '[role="checkbox"]',
            ],
        ),
        'radio': FrameworkPattern(
            class_pattern=r'MuiRadio',
            role='radio',
            selector_hints=[
                '.MuiRadio-root input',
                '[role="radio"]',
            ],
        ),
        'dialog': FrameworkPattern(
            class_pattern=r'MuiDialog|MuiModal',
            role='dialog',
            selector_hints=[
                '.MuiDialog-paper',
                '[role="dialog"]',
            ],
        ),
    },
    'ant_design': {
        'button': FrameworkPattern(
            class_pattern=r'ant-btn',
            selector_hints=[
                '.ant-btn',
                'button.ant-btn',
            ],
        ),
        'input': FrameworkPattern(
            class_pattern=r'ant-input',
            selector_hints=[
                '.ant-input',
                'input.ant-input',
            ],
        ),
        'select': FrameworkPattern(
            class_pattern=r'ant-select',
            selector_hints=[
                '.ant-select-selector',
                '.ant-select',
            ],
        ),
        'option': FrameworkPattern(
            class_pattern=r'ant-select-item',
            selector_hints=[
                '.ant-select-item-option',
                '.ant-select-dropdown .ant-select-item',
            ],
        ),
        'menu_item': FrameworkPattern(
            class_pattern=r'ant-menu-item',
            selector_hints=[
                '.ant-menu-item',
                '.ant-dropdown-menu-item',
            ],
        ),
        'checkbox': FrameworkPattern(
            class_pattern=r'ant-checkbox',
            selector_hints=[
                '.ant-checkbox-input',
                '.ant-checkbox-wrapper',
            ],
        ),
        'modal': FrameworkPattern(
            class_pattern=r'ant-modal',
            role='dialog',
            selector_hints=[
                '.ant-modal-content',
                '.ant-modal-body',
            ],
        ),
    },
    'chakra': {
        'button': FrameworkPattern(
            class_pattern=r'chakra-button',
            selector_hints=[
                '.chakra-button',
                'button.chakra-button',
            ],
        ),
        'input': FrameworkPattern(
            class_pattern=r'chakra-input',
            selector_hints=[
                '.chakra-input',
                'input.chakra-input',
            ],
        ),
        'select': FrameworkPattern(
            class_pattern=r'chakra-select',
            selector_hints=[
                '.chakra-select',
                'select.chakra-select',
            ],
        ),
        'modal': FrameworkPattern(
            class_pattern=r'chakra-modal',
            role='dialog',
            selector_hints=[
                '.chakra-modal__content',
                '[role="dialog"]',
            ],
        ),
    },
    'react_select': {
        'container': FrameworkPattern(
            class_pattern=r'react-select',
            selector_hints=[
                '.react-select__control',
                '[class*="react-select"]',
            ],
        ),
        'input': FrameworkPattern(
            class_pattern=r'__input',
            selector_hints=[
                '.react-select__input input',
                '[class*="__input"] input',
            ],
        ),
        'menu': FrameworkPattern(
            class_pattern=r'__menu',
            selector_hints=[
                '.react-select__menu',
                '[class*="__menu"]',
            ],
        ),
        'option': FrameworkPattern(
            class_pattern=r'__option',
            role='option',
            selector_hints=[
                '.react-select__option',
                '[class*="__option"]',
                '[role="option"]',
            ],
        ),
    },
    'bootstrap': {
        'button': FrameworkPattern(
            class_pattern=r'btn(-|$)',
            selector_hints=[
                '.btn',
                'button.btn',
                '.btn-primary',
                '.btn-secondary',
            ],
        ),
        'input': FrameworkPattern(
            class_pattern=r'form-control',
            selector_hints=[
                '.form-control',
                'input.form-control',
            ],
        ),
        'select': FrameworkPattern(
            class_pattern=r'form-select',
            selector_hints=[
                '.form-select',
                'select.form-select',
            ],
        ),
        'dropdown': FrameworkPattern(
            class_pattern=r'dropdown',
            selector_hints=[
                '.dropdown-toggle',
                '.dropdown-menu',
            ],
        ),
        'dropdown_item': FrameworkPattern(
            class_pattern=r'dropdown-item',
            selector_hints=[
                '.dropdown-item',
                '.dropdown-menu a',
            ],
        ),
        'modal': FrameworkPattern(
            class_pattern=r'modal',
            role='dialog',
            selector_hints=[
                '.modal-content',
                '.modal-body',
            ],
        ),
    },
    'headless_ui': {
        'button': FrameworkPattern(
            role='button',
            aria_pattern={'data-headlessui-state': r'.*'},
            selector_hints=[
                '[data-headlessui-state]',
                'button[data-headlessui-state]',
            ],
        ),
        'listbox': FrameworkPattern(
            role='listbox',
            selector_hints=[
                '[role="listbox"]',
            ],
        ),
        'option': FrameworkPattern(
            role='option',
            selector_hints=[
                '[role="option"]',
                '[data-headlessui-state] [role="option"]',
            ],
        ),
        'menu': FrameworkPattern(
            role='menu',
            selector_hints=[
                '[role="menu"]',
            ],
        ),
        'menu_item': FrameworkPattern(
            role='menuitem',
            selector_hints=[
                '[role="menuitem"]',
            ],
        ),
    },
}


def detect_framework(classes: Set[str]) -> Optional[str]:
    """
    Detect which UI framework a page uses based on class names.
    
    Args:
        classes: Set of all class names found on page
        
    Returns:
        Framework name or None if not detected
    """
    class_string = ' '.join(classes)
    
    scores: Dict[str, int] = {}
    
    for framework, patterns in FRAMEWORK_SIGNATURES.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, class_string, re.IGNORECASE):
                score += 1
        if score > 0:
            scores[framework] = score
    
    if not scores:
        return None
    
    # Return framework with highest score
    return max(scores.items(), key=lambda x: x[1])[0]


def detect_framework_from_selector(selector: str) -> Optional[str]:
    """Detect framework from a single selector/class string."""
    for framework, patterns in FRAMEWORK_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, selector, re.IGNORECASE):
                return framework
    return None


def get_component_selectors(
    framework: str,
    component_type: str,
) -> List[str]:
    """
    Get selector hints for a specific framework component.
    
    Args:
        framework: Framework name (mui, ant_design, chakra, etc.)
        component_type: Component type (button, input, select, etc.)
        
    Returns:
        List of selector patterns to try
    """
    framework_patterns = FRAMEWORK_COMPONENTS.get(framework, {})
    pattern = framework_patterns.get(component_type)
    
    if pattern:
        return pattern.selector_hints
    return []


def get_framework_selector_for_text(
    framework: str,
    text: str,
    component_type: Optional[str] = None,
) -> List[str]:
    """
    Generate framework-specific selectors for finding element with text.
    
    Args:
        framework: Detected framework name
        text: Text content to find
        component_type: Optional hint about component type
        
    Returns:
        List of selectors to try
    """
    selectors = []
    escaped_text = text.replace('"', '\\"')
    
    # Get all component patterns if no specific type
    types_to_check = [component_type] if component_type else [
        'button', 'menu_item', 'option', 'tab'
    ]
    
    framework_patterns = FRAMEWORK_COMPONENTS.get(framework, {})
    
    for comp_type in types_to_check:
        pattern = framework_patterns.get(comp_type)
        if not pattern:
            continue
        
        for hint in pattern.selector_hints:
            # Combine selector hint with text matching
            selectors.append(f'{hint}:has-text("{escaped_text}")')
            
            # Also try >> chained with text
            selectors.append(f'{hint} >> text="{escaped_text}"')
    
    return selectors


def infer_component_type(
    tag: str,
    role: Optional[str],
    classes: str,
) -> Optional[str]:
    """
    Infer component type from element properties.
    
    Args:
        tag: HTML tag name
        role: ARIA role if present
        classes: Class name string
        
    Returns:
        Inferred component type or None
    """
    # Role-based inference (most reliable)
    role_map = {
        'button': 'button',
        'link': 'button',  # Often styled as button
        'menuitem': 'menu_item',
        'option': 'option',
        'tab': 'tab',
        'checkbox': 'checkbox',
        'radio': 'radio',
        'textbox': 'input',
        'combobox': 'select',
        'listbox': 'select',
        'dialog': 'dialog',
    }
    
    if role in role_map:
        return role_map[role]
    
    # Tag-based inference
    tag_map = {
        'button': 'button',
        'a': 'button',
        'input': 'input',
        'textarea': 'input',
        'select': 'select',
    }
    
    if tag in tag_map:
        return tag_map[tag]
    
    # Class-based inference (check all frameworks)
    class_lower = classes.lower()
    
    if any(x in class_lower for x in ['button', 'btn']):
        return 'button'
    if any(x in class_lower for x in ['input', 'textfield']):
        return 'input'
    if any(x in class_lower for x in ['select', 'dropdown']):
        return 'select'
    if any(x in class_lower for x in ['menu-item', 'menuitem', 'dropdown-item']):
        return 'menu_item'
    if any(x in class_lower for x in ['option']):
        return 'option'
    if any(x in class_lower for x in ['tab']):
        return 'tab'
    if any(x in class_lower for x in ['modal', 'dialog']):
        return 'dialog'
    
    return None


# JavaScript to detect frameworks on a page
DETECT_FRAMEWORKS_JS = r'''() => {
    const classSet = new Set();
    
    // Collect all class names
    document.querySelectorAll('[class]').forEach(el => {
        if (el.className && typeof el.className === 'string') {
            el.className.split(' ').forEach(c => {
                if (c.trim()) classSet.add(c.trim());
            });
        }
    });
    
    return Array.from(classSet);
}'''
