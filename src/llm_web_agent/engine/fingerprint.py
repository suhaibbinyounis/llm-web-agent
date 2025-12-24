"""
Element Fingerprinting - Stable identifiers for elements across page reloads.

Fingerprints use multiple signals to create IDs that:
- Survive page refreshes and re-renders
- Handle dynamic class names (CSS-in-JS)
- Work with framework-generated IDs
- Remain stable across minor DOM changes
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set


# Classes that indicate dynamic generation (should be ignored)
DYNAMIC_CLASS_PATTERNS = [
    r'^css-[a-zA-Z0-9]+$',        # Emotion/styled-components
    r'^sc-[a-zA-Z]+$',            # Styled-components
    r'^_[a-zA-Z0-9]{5,}$',        # CSS Modules hashes
    r'^[a-zA-Z]+__[a-zA-Z]+_[a-zA-Z0-9]+$',  # BEM with hash
    r'^jsx-\d+$',                 # Next.js styled-jsx
    r'^svelte-[a-z0-9]+$',        # Svelte
    r'^styles_[a-zA-Z]+__[a-zA-Z0-9]+$',  # CSS Modules
]

# Classes that are stable and meaningful
STABLE_CLASS_PREFIXES = [
    'Mui', 'ant-', 'chakra-', 'btn', 'button', 'input', 'form',
    'nav', 'header', 'footer', 'sidebar', 'menu', 'modal', 'dialog',
    'card', 'list', 'item', 'container', 'wrapper', 'content',
]


def _is_dynamic_class(class_name: str) -> bool:
    """Check if a class name appears to be dynamically generated."""
    for pattern in DYNAMIC_CLASS_PATTERNS:
        if re.match(pattern, class_name):
            return True
    return False


def _is_stable_class(class_name: str) -> bool:
    """Check if a class name is likely stable/semantic."""
    class_lower = class_name.lower()
    for prefix in STABLE_CLASS_PREFIXES:
        if class_lower.startswith(prefix.lower()):
            return True
    return False


def sanitize_classname(class_string: str) -> str:
    """
    Extract stable, meaningful classes from a class string.
    
    Filters out dynamically-generated class names (CSS-in-JS, CSS Modules)
    while keeping semantic class names.
    
    Args:
        class_string: Space-separated class names
        
    Returns:
        Filtered, sorted class string
    """
    if not class_string:
        return ""
    
    classes = class_string.split()
    stable_classes = []
    
    for cls in classes:
        cls = cls.strip()
        if not cls:
            continue
        # Keep if explicitly stable OR not dynamically generated
        if _is_stable_class(cls) or not _is_dynamic_class(cls):
            # Additional filter: skip very long class names (likely hashes)
            if len(cls) <= 50:
                stable_classes.append(cls)
    
    # Sort for consistency
    stable_classes.sort()
    
    # Take max 5 most meaningful classes
    return ' '.join(stable_classes[:5])


def normalize_text(text: str) -> str:
    """
    Normalize text content for fingerprinting.
    
    - Lowercase
    - Collapse whitespace
    - Remove leading/trailing whitespace
    - Truncate to reasonable length
    """
    if not text:
        return ""
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text.strip().lower())
    
    # Truncate long text (we only need enough for identification)
    return text[:100]


def normalize_position(nth_child: int, total_siblings: int) -> str:
    """
    Create position hint for fingerprint.
    
    Uses relative position to handle dynamic sibling counts.
    """
    if total_siblings <= 1:
        return "only"
    elif nth_child == 1:
        return "first"
    elif nth_child == total_siblings:
        return "last"
    elif nth_child <= total_siblings // 3:
        return "start"
    elif nth_child >= total_siblings * 2 // 3:
        return "end"
    else:
        return "middle"


@dataclass
class FingerprintInput:
    """Input data for generating element fingerprint."""
    text: str
    tag: str
    aria_label: Optional[str] = None
    role: Optional[str] = None
    class_name: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    placeholder: Optional[str] = None
    data_testid: Optional[str] = None
    href: Optional[str] = None
    nth_child: int = 1
    sibling_count: int = 1


def generate_fingerprint(element: FingerprintInput) -> str:
    """
    Generate stable fingerprint for an element.
    
    The fingerprint is a short hash derived from multiple element signals,
    designed to remain stable across:
    - Page refreshes
    - Minor DOM re-renders
    - Dynamic class name changes
    
    Args:
        element: FingerprintInput with element attributes
        
    Returns:
        12-character hex fingerprint
    """
    signals = []
    
    # Primary signals (most stable)
    if element.data_testid:
        signals.append(f"tid:{element.data_testid}")
    
    if element.name:
        signals.append(f"name:{element.name}")
    
    if element.aria_label:
        signals.append(f"aria:{normalize_text(element.aria_label)}")
    
    # Secondary signals
    signals.append(f"tag:{element.tag}")
    
    if element.role:
        signals.append(f"role:{element.role}")
    
    if element.type:
        signals.append(f"type:{element.type}")
    
    # Text content (normalized)
    text = normalize_text(element.text)
    if text:
        signals.append(f"text:{text}")
    
    if element.placeholder:
        signals.append(f"ph:{normalize_text(element.placeholder)}")
    
    # Stable classes
    stable_classes = sanitize_classname(element.class_name or "")
    if stable_classes:
        signals.append(f"cls:{stable_classes}")
    
    # Position hint (for disambiguation)
    position = normalize_position(element.nth_child, element.sibling_count)
    signals.append(f"pos:{position}")
    
    # URL path for links (not full URL)
    if element.href and element.href.startswith('/'):
        signals.append(f"href:{element.href}")
    
    # Create hash
    signal_string = '|'.join(signals)
    return hashlib.md5(signal_string.encode()).hexdigest()[:12]


def generate_selector_priority_list(
    element: FingerprintInput,
    fingerprint: str,
) -> List[str]:
    """
    Generate ordered list of selectors for an element.
    
    Priority order:
    1. data-testid (most reliable when present)
    2. ID (if stable-looking)
    3. name attribute
    4. aria-label
    5. Text-based selector
    6. Class + tag combination
    
    Args:
        element: FingerprintInput with element attributes
        fingerprint: The element's fingerprint
        
    Returns:
        List of selectors in priority order
    """
    selectors = []
    
    # 1. data-testid (best)
    if element.data_testid:
        selectors.append(f'[data-testid="{element.data_testid}"]')
    
    # 2. name attribute
    if element.name:
        selectors.append(f'[name="{element.name}"]')
    
    # 3. aria-label
    if element.aria_label:
        label = element.aria_label.replace('"', '\\"')
        selectors.append(f'[aria-label="{label}"]')
    
    # 4. Placeholder for inputs
    if element.placeholder and element.tag in ('input', 'textarea'):
        ph = element.placeholder.replace('"', '\\"')
        selectors.append(f'{element.tag}[placeholder="{ph}"]')
    
    # 5. Text-based (for buttons/links)
    if element.text and element.tag in ('button', 'a'):
        text = element.text.strip()[:50]
        selectors.append(f'text="{text}"')
    
    # 6. Stable class + tag
    stable_classes = sanitize_classname(element.class_name or "")
    if stable_classes:
        first_class = stable_classes.split()[0]
        selectors.append(f'{element.tag}.{first_class}')
    
    return selectors


# JavaScript to extract fingerprint data from all interactive elements
EXTRACT_FINGERPRINT_DATA_JS = r'''() => {
    const elements = [];
    
    // Selector for interactive and identifiable elements
    const selector = [
        'button', 'a', 'input', 'select', 'textarea', 'label',
        '[role="button"]', '[role="link"]', '[role="menuitem"]',
        '[role="option"]', '[role="tab"]', '[role="checkbox"]',
        '[role="radio"]', '[role="switch"]', '[role="textbox"]',
        '[data-testid]', '[aria-label]',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    ].join(', ');
    
    document.querySelectorAll(selector).forEach((el, index) => {
        // Skip invisible elements
        if (!el.offsetParent && el.tagName.toLowerCase() !== 'body') return;
        
        // Get text content
        let text = '';
        const tag = el.tagName.toLowerCase();
        if (tag === 'input') {
            text = el.placeholder || el.value || '';
        } else {
            // Get direct text only (not from children)
            const directText = Array.from(el.childNodes)
                .filter(n => n.nodeType === Node.TEXT_NODE)
                .map(n => n.textContent.trim())
                .join(' ');
            text = directText || (el.innerText || '').split('\n')[0] || '';
        }
        
        // Calculate position among siblings
        let nthChild = 1;
        let siblingCount = 1;
        if (el.parentElement) {
            const siblings = Array.from(el.parentElement.children);
            siblingCount = siblings.length;
            nthChild = siblings.indexOf(el) + 1;
        }
        
        // Get bounding rect
        const rect = el.getBoundingClientRect();
        
        elements.push({
            text: text.slice(0, 200),
            tag: tag,
            ariaLabel: el.getAttribute('aria-label'),
            role: el.getAttribute('role'),
            className: el.className && typeof el.className === 'string' ? el.className : '',
            name: el.getAttribute('name'),
            type: el.getAttribute('type'),
            placeholder: el.getAttribute('placeholder'),
            dataTestid: el.getAttribute('data-testid'),
            href: tag === 'a' ? el.getAttribute('href') : null,
            id: el.id,
            nthChild: nthChild,
            siblingCount: siblingCount,
            rect: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
            },
            isClickable: ['a', 'button'].includes(tag) || 
                         el.getAttribute('role') === 'button' ||
                         el.onclick !== null,
        });
    });
    
    return elements;
}'''
