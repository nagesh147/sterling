const fs = require('fs');
const path = require('path');

function walk(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach(file => {
    file = path.join(dir, file);
    const stat = fs.statSync(file);
    if (stat && stat.isDirectory()) {
      results = results.concat(walk(file));
    } else {
      results.push(file);
    }
  });
  return results;
}

const files = walk('frontend/src');
let changed = 0;

files.forEach(file => {
  if (file.endsWith('.tsx') || file.endsWith('.ts')) {
    let code = fs.readFileSync(file, 'utf8');
    
    // Replace borderRadius: <expr> with borderRadius: 0
    // Skip if it contains '%' (usually '50%')
    const newCode = code.replace(/borderRadius:\s*([^,}]+)/g, (match, val) => {
      if (val.includes('%')) return match; // Keep '50%'
      if (val.trim() === '0') return match;
      return 'borderRadius: 0';
    });
    
    if (newCode !== code) {
      fs.writeFileSync(file, newCode);
      changed++;
    }
  } else if (file.endsWith('.css')) {
    let code = fs.readFileSync(file, 'utf8');
    
    const newCode = code.replace(/border-radius:\s*([^;]+)/g, (match, val) => {
      if (val.includes('%')) return match; 
      if (val.includes('0 !important')) return match;
      if (val.trim() === '0' || val.trim() === '0px') return match;
      return 'border-radius: 0';
    });
    
    if (newCode !== code) {
      fs.writeFileSync(file, newCode);
      changed++;
    }
  }
});
console.log('Changed files:', changed);
