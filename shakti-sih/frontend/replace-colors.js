const fs = require('fs');
const path = require('path');

const directoryPath = 'C:\\Users\\SREEJEETA\\OneDrive\\Desktop\\tejas\\shakti-sih\\frontend\\src';

const replacements = {
  // Chart Grid Lines
  'stroke="#1e293b"': 'stroke="var(--border)"',
  'stroke="hsl(217, 33%, 17%)"': 'stroke="var(--border)"',
  
  // Chart Axis Ticks
  'stroke="#64748b"': 'stroke="var(--muted-foreground)"',
  'fill="hsl(215, 20%, 55%)"': 'fill="var(--muted-foreground)"',
  
  // Danger (was red)
  'stroke="#ef4444"': 'stroke="var(--danger)"',
  'color: "#ef4444"': 'color: "var(--danger)"',
  
  // Accent/Attention (was amber/orange)
  'stroke="#f59e0b"': 'stroke="var(--accent)"',
  'color: "#f59e0b"': 'color: "var(--accent)"',
  'bg-amber-400': 'bg-accent',
  'text-amber-400': 'text-accent',
  
  // Primary Series (was blue)
  'stroke="#3b82f6"': 'stroke="var(--series-primary, #4f7ea8)"',
  'color: "#3b82f6"': 'color: "var(--series-primary, #4f7ea8)"',
  
  // Secondary Series (was plum)
  'stroke="#a855f7"': 'stroke="var(--series-secondary, #8a76a8)"',
  'color: "#a855f7"': 'color: "var(--series-secondary, #8a76a8)"',
  
  // Forecast Uncertainty (was cyan)
  'stroke="#22d3ee"': 'stroke="var(--series-uncertainty, #6fb3c9)"',
  'color: "#22d3ee"': 'color: "var(--series-uncertainty, #6fb3c9)"',
  'fill="rgba(34, 211, 238, 0.12)"': 'fill="var(--series-uncertainty, #6fb3c9)" fillOpacity={0.12}',
  'bg-cyan-400': 'bg-[var(--series-uncertainty,#6fb3c9)]',
  'text-cyan-400': 'text-[var(--series-uncertainty,#6fb3c9)]',
  'borderTop: "2px dashed #22d3ee"': 'borderTop: "2px dashed var(--series-uncertainty, #6fb3c9)"',

  // Tooltip Backgrounds
  'backgroundColor: "hsl(222, 47%, 11%)"': 'backgroundColor: "var(--card)"',
  'border: "1px solid hsl(217, 33%, 17%)"': 'border: "1px solid var(--border)"',
  
  // Area Fills
  'fill="hsl(222, 47%, 11%)"': 'fill="var(--card)"',
  'fill="rgba(251, 191, 36, 0.12)"': 'fill="var(--accent)" fillOpacity={0.12}',
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
