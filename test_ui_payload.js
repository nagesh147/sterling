const fs = require('fs');
const content = fs.readFileSync('frontend/src/components/scalping/ScalpingTab.tsx', 'utf8');
console.log(content.match(/useSetScalpingConfig/));
