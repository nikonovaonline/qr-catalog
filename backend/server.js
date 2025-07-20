const express = require('express');
const fs = require('fs');
const app = express();
const port = 3000;

const data = JSON.parse(fs.readFileSync('./data/catalog.json', 'utf-8'));

app.get('/api/items/:id', (req, res) => {
  const item = data.find((i) => i.id === req.params.id);
  if (item) {
    res.json(item);
  } else {
    res.status(404).json({ error: 'Item not found' });
  }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
