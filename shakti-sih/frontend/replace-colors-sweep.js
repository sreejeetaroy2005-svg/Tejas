const fs = require('fs');
const path = require('path');

const directoryPath = 'C:\\Users\\SREEJEETA\\OneDrive\\Desktop\\tejas\\shakti-sih\\frontend\\src';

const replacements = {
  // Fix the missed ones
  '#1e293b': 'var(--border)',
  '#64748b': 'var(--muted-foreground)',
  '#ef4444': 'var(--danger)',
  '#f59e0b': 'var(--accent)',
  '#3b82f6': 'var(--series-primary, #4f7ea8)',
  '#a855f7': 'var(--series-secondary, #8a76a8)',
  '#22d3ee': 'var(--series-uncertainty, #6fb3c9)',
  '#f97316': 'var(--series-primary, #4f7ea8)', // Was gas interference orange, should be steel blue
  '#22c55e': 'var(--safe)',
};

function processDirectory(dir) {
  fs.readdirSync(dir).forEach(file => {
    const fullPath = path.join(dir, file);
    if (fs.statSync(fullPath).isDirectory()) {
      processDirectory(fullPath);
    } else if (fullPath.endsWith('.tsx') || fullPath.endsWith('.ts')) {
      let content = fs.readFileSync(fullPath, 'utf8');
      let changed = false;
      for (const [key, value] of Object.entries(replacements)) {
        if (content.includes(key)) {
          content = content.split(key).join(value);
          changed = true;
        }
      }
      if (changed) {
        fs.writeFileSync(fullPath, content, 'utf8');
        console.log(`Updated: ${fullPath}`);
      }
    }
  });
}

processDirectory(directoryPath);
