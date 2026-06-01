const express = require('express');
const app = express();
const path = require('path');

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static('public'));

app.get('/', (req, res) => {
    res.render('index', { query: null });
});

app.get('/search', (req, res) => {
    const q = req.query.q;
    // VULNERABILITY: Directly rendering input without sanitization
    // The view uses <%- query %> which interprets HTML
    res.render('index', { query: q });
});

const PORT = 3000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Vulnerable App running on port ${PORT}`);
});
