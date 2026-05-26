const fs = require('fs');
let file = fs.readFileSync('src/components/SimpleSettings.tsx', 'utf8');

const replacements = [
  [/var\(--text-primary\)/g, 'var(--t-bright)'],
  [/var\(--text-muted\)/g, 'var(--t-bright)'],
  [/var\(--text-faint\)/g, 'var(--t-dim)'],
  [/var\(--text-dim\)/g, 'var(--t-dim)'],
  [/var\(--bg-card\)/g, 'var(--t-bg)'],
  [/var\(--bg-surface\)/g, 'var(--t-bg2)'],
  [/var\(--bg-input\)/g, 'var(--t-bg2)'],
  [/var\(--bg\)/g, 'var(--t-bg2)'],
  [/var\(--border-light\)/g, 'var(--t-border)'],
  [/var\(--border\)/g, 'var(--t-border)'],
  [/var\(--accent\)/g, 'var(--t-blue)'], // Let's use blue for accent usually
  [/var\(--danger\)/g, 'var(--t-red)'],
  [/#10b981/g, 'var(--t-green)'],
  [/#ff4757/g, 'var(--t-red)'],
  [/#86c9a8/g, 'var(--t-green)'],
  [/#f0c040/g, 'var(--t-amber)'],
  [/#a78bfa/g, 'var(--t-purple)'],
  [/#333/g, 'var(--t-border)'],
  [/#cc4444/g, 'var(--t-red)'],
  [/#4499cc/g, 'var(--t-blue)'],
  [/#0d1520/g, 'var(--t-bg2)'],
  [/#88aaff/g, 'var(--t-blue)'],
  [/#1a1200/g, 'var(--t-bg2)'],
  [/#1a1400/g, 'var(--t-bg2)'],
  [/#2a2000/g, 'var(--t-bg2)'],
  [/#0f2a1a/g, 'var(--t-bg2)'],
  [/#0a2a14/g, 'var(--t-bg2)'],
  [/#2a0808/g, 'var(--t-bg2)'],
  [/#ffa0a8/g, 'var(--t-red)'],
  [/#44cc88/g, 'var(--t-green)'],
  [/#88dda0/g, 'var(--t-green)'],
  [/borderRadius: 8/g, 'borderRadius: 6'],
  [/borderRadius: 5/g, 'borderRadius: 4'],
];

replacements.forEach(([regex, repl]) => {
  file = file.replace(regex, repl);
});

fs.writeFileSync('src/components/SimpleSettings.tsx', file);
console.log('Done mapping variables in SimpleSettings.tsx');
