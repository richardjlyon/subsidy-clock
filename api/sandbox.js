import { decodeCode, formatGBP } from './decode.js';

export default function handler(req, res) {
  const { id } = req.query;
  
  if (!id) {
    return res.redirect('/buy');
  }
  
  const decoded = decodeCode(id);
  const totalCost = decoded ? decoded.totalCost : 0;
  const formattedTotal = totalCost > 0 ? formatGBP(totalCost) : 'money';
  
  const host = req.headers.host || 'subsidyclock.co.uk';
  const protocol = req.headers['x-forwarded-proto'] || 'https';
  const imageUrl = `${protocol}://${host}/api/sandbox/image/${id}`;

  res.setHeader('Content-Type', 'text/html');
  res.status(200).send(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>What Could The Subsidy Clock Buy?</title>
  <meta property="og:title" content="What Could The Subsidy Clock Buy?">
  <meta property="og:description" content="I spent ${formattedTotal} of the UK energy subsidy clock! See my receipt.">
  <meta property="og:image" content="${imageUrl}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="What Could The Subsidy Clock Buy?">
  <meta name="twitter:description" content="I spent ${formattedTotal} of the UK energy subsidy clock! See my receipt.">
  <meta name="twitter:image" content="${imageUrl}">
  <script>
    window.location.replace('/buy#b=' + encodeURIComponent("${id}"));
  </script>
</head>
<body>
  <p>Redirecting to the Subsidy Clock...</p>
</body>
</html>`);
}
