const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, 'frontend-kit');
const families = [
  ['components', ['button', 'card', 'input', 'modal', 'navigation', 'table']],
  ['email-blocks', ['hero', 'announcement', 'product', 'testimonial', 'footer', 'newsletter']],
  ['content-presets', ['welcome', 'launch', 'weekly', 'event', 'receipt', 'reengagement']],
  ['tokens', ['color', 'spacing', 'type', 'shadow', 'radius', 'motion']],
  ['accessibility', ['keyboard', 'labels', 'focus', 'contrast', 'screen-reader', 'forms']],
  ['ui-patterns', ['dashboard', 'campaign', 'audience', 'analytics', 'settings', 'onboarding']],
];

const descriptions = {
  components: 'A reusable interface component with consistent states and semantic markup guidance.',
  'email-blocks': 'A flexible email template block intended for visual campaign composition.',
  'content-presets': 'A copy and layout preset for a purposeful customer message.',
  tokens: 'A design token reference for maintaining visual consistency across the interface.',
  accessibility: 'An accessibility implementation note for inclusive, reliable interactions.',
  'ui-patterns': 'A page-level interface pattern for a focused product workflow.',
};

for (const [section, names] of families) {
  for (let index = 1; index <= 190; index += 1) {
    const name = names[(index - 1) % names.length];
    const file = path.join(root, section, `${String(index).padStart(3, '0')}-${name}.md`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const title = `${name.replace(/\b\w/g, letter => letter.toUpperCase())} ${index}`;
    const body = `# ${title}\n\n${descriptions[section]}\n\n## Intent\n\nProvide a clear, focused experience that works on desktop and mobile.\n\n## Visual direction\n\n- Warm neutral canvas with high-contrast ink text\n- Coral used sparingly for primary emphasis\n- Rounded surfaces and calm, generous spacing\n\n## Implementation notes\n\nUse semantic HTML, visible focus states, and responsive layout rules.\n\n## Variant\n\nVariant ${index} is ready to be adapted to the campaign dashboard.\n`;
    fs.writeFileSync(file, body, 'utf8');
  }
}

console.log('Created 1,140 design-kit reference files.');
