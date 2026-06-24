import fs from 'node:fs';

const requiredFiles = [
  'components/Affiliates.tsx',
  'components/AffiliateWallet.tsx',
];

const missing = [];

for (const file of requiredFiles) {
  if (!fs.existsSync(file)) {
    missing.push(`${file} (missing file)`);
    continue;
  }

  const content = fs.readFileSync(file, 'utf8');
  if (!content.includes('AffiliateDisclosure')) {
    missing.push(`${file} (AffiliateDisclosure not referenced)`);
  }
}

if (missing.length > 0) {
  console.error('FAIL: Affiliate disclosure check failed');
  for (const item of missing) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

console.log('PASS: Affiliate disclosure present on all required affiliate surfaces');
