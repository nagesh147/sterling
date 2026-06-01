const http = require('http');

const options = {
  hostname: '127.0.0.1',
  port: 8000,
  path: '/api/v1/scalping/config',
  method: 'GET'
};

const req = http.request(options, res => {
  let body = '';
  res.on('data', d => body += d);
  res.on('end', () => {
    const config = JSON.parse(body).config;
    config.use_optimized = true;
    
    // Now POST it back
    const postData = JSON.stringify(config);
    const postOptions = {
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/scalping/config',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    };
    
    const postReq = http.request(postOptions, res2 => {
      let body2 = '';
      res2.on('data', d => body2 += d);
      res2.on('end', () => {
        console.log('STATUS:', res2.statusCode);
        console.log('RESPONSE:', body2);
      });
    });
    postReq.write(postData);
    postReq.end();
  });
});
req.end();
