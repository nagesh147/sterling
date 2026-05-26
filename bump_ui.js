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
    let original = code;
    
    // Bump inline font sizes by 2 to 3 px
    code = code.replace(/fontSize:\s*(\d+)/g, (match, sizeStr) => {
      let size = parseInt(sizeStr, 10);
      if (size < 18) {
        size += 2; 
      }
      return `fontSize: ${size}`;
    });
    
    // Bump 'Ypx Xpx' padding padding
    code = code.replace(/padding:\s*['"](\d+)px\s+(\d+)px['"]/g, (match, py, px) => {
      let ny = parseInt(py, 10) + 4;
      let nx = parseInt(px, 10) + 6;
      return `padding: '${ny}px ${nx}px'`;
    });
    
    // Bump number-only padding
    code = code.replace(/padding:\s*(\d+)(?!px|%|em|rem)/g, (match, pStr) => {
      let p = parseInt(pStr, 10);
      if (p < 32 && p > 0) p += 4;
      return `padding: ${p}`;
    });

    if (code !== original) {
      fs.writeFileSync(file, code);
      changed++;
    }
  }
});
console.log('Changed files:', changed);
