"""WCAG luminance of browser-resolved colors; no additional dependencies."""
import json
import io
import math
from PIL import Image


def ratio(a, b):
    def luminance(rgb):
        channels = [v / 255 for v in rgb[:3]]
        return sum((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) * w
                   for v, w in zip(channels, [.2126, .7152, .0722]))
    x, y = sorted([luminance(a), luminance(b)])
    return (y + .05) / (x + .05)


# Include inherited colors and alpha compositing. For gradients use every stop
# conservatively. Sibling artwork/photos require a separate pixel measurement.
READ_COLORS = r"""(rootSelector) => {
    const parse = value => {
        const p = value.match(/[\d.]+/g).map(Number);
        return [...p.slice(0,3), p.length > 3 ? p[3] : 1];
    };
    const over = (top, bottom) => [...top.slice(0,3).map((v,i) => v*top[3]+bottom[i]*(1-top[3])), 1];
    const path = el => el.id ? '#' + el.id : el.tagName.toLowerCase() + [...el.classList].map(c => '.'+c).join('');
    const unique = rows => [...new Map(rows.map(r=>[JSON.stringify(r),r])).values()];
    const backgrounds = el => {
        if (!el) return [[255,255,255,1]];
        const s = getComputedStyle(el), below = backgrounds(el.parentElement);
        const base = unique(below.map(bg => over(parse(s.backgroundColor),bg)));
        if (s.backgroundImage === 'none') return base;
        const stops = s.backgroundImage.match(/rgba?\([^)]+\)/g) || [];
        return stops.length ? unique(stops.flatMap(c => base.map(bg => over(parse(c),bg)))) : base;
    };
    const visible = el => el.checkVisibility({checkVisibilityCSS:true, checkOpacity:true}) &&
        !el.closest('.sr-only, [aria-hidden="true"]') && el.getBoundingClientRect().width > 1;
    const rows = [], root = document.querySelector(rootSelector);
    for (const el of [root, ...root.querySelectorAll('*')]) {
        if (!visible(el) || el.closest('svg, .theme-swatch, .moon-seal, .note-illustration, .hero-doodle')) continue;
        const s = getComputedStyle(el);
        let opacity = 1;
        for (let p=el;p;p=p.parentElement) opacity *= Number(getComputedStyle(p).opacity);
        const disabled = !!el.closest(':disabled');
        const add = (kind, color, bg, minimum, pseudo='') => {
            const fg = parse(color); fg[3] *= opacity;
            rows.push({selector:path(el)+pseudo,kind,fg:bg.map(b=>over(fg,b)),bg,minimum,
                disabled,size:s.fontSize,weight:s.fontWeight});
        };
        const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.6667 && Number(s.fontWeight) >= 700);
        if (el.matches('.favorite-button,.icon-button,.view-switch button,.trial-delete,.step-actions button,.delete-ingredient,.search-box,.theme-toggle'))
            add('icon',s.color,backgrounds(el),3);
        if (el.matches('.button,.search-box,.chip,.filters select,.icon-button,.auth-card input,.form-body input:not([type=file]):not([type=checkbox]),.form-body textarea,.form-body select,.photo-drop,.add-row-button,.trial-delete,.theme-toggle,.theme-option,.method-option,.catalog-kind-label select')) {
            if (parseFloat(s.borderTopWidth) > 0 && !el.matches('.detail-photo>.icon-button'))
                add('border',s.borderTopColor,backgrounds(el.parentElement),3);
        }
        if (el.matches('.view-switch button.active')) {
            const shadowColor = s.boxShadow.match(/rgba?\([^)]+\)/);
            if (!shadowColor) throw new Error('Missing selected view indicator');
            add('selected',shadowColor[0],backgrounds(el),3);
        }
        if (el.matches('.nav-item.active')) {
            const ps = getComputedStyle(el,'::after');
            if (ps.content === '""' && parseFloat(ps.height) > 0)
                add('selected',ps.backgroundColor,backgrounds(el.parentElement),3);
        }
        if (el.matches(':focus-visible')) {
            const ring = el.matches('.search-box input') ? el.parentElement : el;
            const rs = getComputedStyle(ring);
            if (rs.outlineStyle === 'none' || parseFloat(rs.outlineWidth) < 2)
                throw new Error('Missing visible focus: '+path(el));
            add('focus',rs.outlineColor,backgrounds(ring.parentElement),3);
        }
        if ([...el.childNodes].some(n=>n.nodeType===3 && n.textContent.trim()))
            add('text',s.color,backgrounds(el),large ? 3 : 4.5);
        if (el.matches('input:not([type=checkbox]):not([type=file]),textarea,select')) {
            add('text',s.color,backgrounds(el),4.5);
            if (el.placeholder) {
                const ps = getComputedStyle(el,'::placeholder');
                const c = parse(ps.color); c[3] *= Number(ps.opacity);
                add('placeholder',`rgba(${c.join(',')})`,backgrounds(el),4.5);
            }
        }
        for (const pseudo of ['::before','::after']) {
            const ps = getComputedStyle(el,pseudo);
            if (ps.content && !['none','normal','""',"''"].includes(ps.content) && ps.display !== 'none')
                add('pseudo',ps.color,backgrounds(el),3,pseudo);
        }
    }
    return rows;
}"""


def measurements(page, root='body'):
    rows = page.evaluate(READ_COLORS, root)
    for row in rows:
        row['ratio'] = min(ratio(fg, bg) for fg, bg in zip(row['fg'], row['bg']))
    return rows


def assert_text_contrast(test, page, root='body'):
    rows = measurements(page, root)
    failures = [r for r in rows if not r['disabled'] and r['ratio'] < r['minimum']]
    unique = {(r['selector'], r['kind'], round(r['ratio'], 3)): r for r in failures}
    test.assertEqual(list(unique), [], json.dumps(list(unique.values()), ensure_ascii=False, indent=2))
    return rows


def artwork_measurements(page, selector):
    """Sample the rendered background at glyph pixels, including sibling artwork.

    Compare screenshots with/without text fill (same layout); use the full computed
    foreground rather than antialiased edge pixels. Text shadows are ignored.
    """
    page.locator(selector).scroll_into_view_if_needed()
    page.evaluate('document.fonts.ready')
    reset_shadow = page.add_style_tag(content=f'{selector}, {selector} * {{text-shadow:none!important}}')
    try:
        nodes = page.locator(selector).evaluate(r'''root => {
            const result=[], walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
                const node=walker.currentNode, el=node.parentElement;
                if (!node.textContent.trim() || el.closest('svg,.hero-doodle')) continue;
                if (!el.checkVisibility({checkVisibilityCSS:true,checkOpacity:true})) continue;
                const range=document.createRange();range.selectNodeContents(node);
                const s=getComputedStyle(el);
                result.push({text:node.textContent.trim(),color:s.color.match(/[\d.]+/g).map(Number),
                    minimum:parseFloat(s.fontSize)>=24 ? 3 : 4.5,
                    rects:[...range.getClientRects()].map(r=>({x:r.x,y:r.y,w:r.width,h:r.height}))});
            }
            return result;
        }''')
        before = Image.open(io.BytesIO(page.screenshot(animations='disabled'))).convert('RGB')
        hide = page.add_style_tag(content=f'{selector}, {selector} * {{-webkit-text-fill-color:transparent!important}}')
        try:
            background = Image.open(io.BytesIO(page.screenshot(animations='disabled'))).convert('RGB')
        finally:
            hide.evaluate('(e)=>e.remove()')
        results = []
        for node in nodes:
            values = []
            for rect in node['rects']:
                for y in range(max(0, math.floor(rect['y'])), min(background.height, math.ceil(rect['y']+rect['h']))):
                    for x in range(max(0, math.floor(rect['x'])), min(background.width, math.ceil(rect['x']+rect['w']))):
                        bg, original = background.getpixel((x, y)), before.getpixel((x, y))
                        if max(abs(a-b) for a,b in zip(bg, original)) > 25:
                            values.append(ratio(node['color'], bg))
            if values:
                results.append(dict(text=node['text'], minimum=node['minimum'], ratio=min(values)))
        return results
    finally:
        reset_shadow.evaluate('(e)=>e.remove()')
