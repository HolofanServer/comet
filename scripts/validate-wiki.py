#!/usr/bin/env python3
"""
Wiki validation script for COMET bot documentation.
Checks for broken links, missing files, and structural issues.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Set
import argparse


class WikiValidator:
    """Validates wiki structure and content."""
    
    def __init__(self, wiki_path: str):
        self.wiki_path = Path(wiki_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def validate(self) -> bool:
        """Run all validation checks."""
        print("🔍 Validating COMET wiki structure...")
        
        if not self.wiki_path.exists():
            self.errors.append(f"Wiki directory not found: {self.wiki_path}")
            return False
        
        self._check_required_files()
        self._check_directory_structure()
        self._check_markdown_files()
        self._check_internal_links()
        self._check_image_references()
        self._check_code_blocks()
        
        self._report_results()
        
        return len(self.errors) == 0
    
    def _check_required_files(self):
        """Check for required wiki files."""
        required_files = [
            "README.md",
            "01-architecture/01-bot-architecture-overview.md",
            "02-core/01-main-bot-class.md",
            "03-cogs/01-cogs-architecture.md",
            "05-development/01-development-setup.md"
        ]
        
        for file_path in required_files:
            full_path = self.wiki_path / file_path
            if not full_path.exists():
                self.errors.append(f"Required file missing: {file_path}")
    
    def _check_directory_structure(self):
        """Check wiki directory structure."""
        expected_dirs = [
            "01-architecture",
            "02-core", 
            "03-cogs",
            "04-utilities",
            "05-development",
            "06-commands",
            "07-operations"
        ]
        
        for dir_name in expected_dirs:
            dir_path = self.wiki_path / dir_name
            if not dir_path.exists():
                self.warnings.append(f"Expected directory missing: {dir_name}")
            elif not dir_path.is_dir():
                self.errors.append(f"Expected directory is not a directory: {dir_name}")
    
    def _check_markdown_files(self):
        """Check markdown file structure and content."""
        md_files = list(self.wiki_path.rglob("*.md"))
        
        if not md_files:
            self.errors.append("No markdown files found in wiki")
            return
        
        for md_file in md_files:
            self._validate_markdown_file(md_file)
    
    def _validate_markdown_file(self, file_path: Path):
        """Validate individual markdown file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            relative_path = file_path.relative_to(self.wiki_path)
            
            if not content.startswith('#'):
                self.warnings.append(f"File missing title: {relative_path}")
            
            if "C.O.M.E.T." not in content and relative_path.name != "README.md":
                self.warnings.append(f"File missing COMET description: {relative_path}")
            
            if len(content.strip()) < 100:
                self.warnings.append(f"File appears to be too short: {relative_path}")
            
            self._check_heading_hierarchy(content, relative_path)
            
        except Exception as e:
            self.errors.append(f"Error reading file {relative_path}: {str(e)}")
    
    def _check_heading_hierarchy(self, content: str, file_path: Path):
        """Check markdown heading hierarchy."""
        lines = content.split('\n')
        heading_levels = []
        
        for line_num, line in enumerate(lines, 1):
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                heading_levels.append((level, line_num))
        
        for i in range(1, len(heading_levels)):
            current_level = heading_levels[i][0]
            prev_level = heading_levels[i-1][0]
            
            if current_level > prev_level + 1:
                line_num = heading_levels[i][1]
                self.warnings.append(
                    f"Heading hierarchy skip in {file_path} at line {line_num}: "
                    f"h{prev_level} to h{current_level}"
                )
    
    def _check_internal_links(self):
        """Check internal wiki links."""
        md_files = list(self.wiki_path.rglob("*.md"))
        
        for md_file in md_files:
            self._check_file_links(md_file)
    
    def _check_file_links(self, file_path: Path):
        """Check links in a specific file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            relative_path = file_path.relative_to(self.wiki_path)
            
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            links = re.findall(link_pattern, content)
            
            for link_text, link_url in links:
                if self._is_internal_link(link_url):
                    self._validate_internal_link(link_url, file_path, relative_path)
        
        except Exception as e:
            self.errors.append(f"Error checking links in {relative_path}: {str(e)}")
    
    def _is_internal_link(self, url: str) -> bool:
        """Check if URL is an internal wiki link."""
        return (
            not url.startswith(('http://', 'https://')) and
            not url.startswith('#') and
            url.endswith('.md')
        )
    
    def _validate_internal_link(self, link_url: str, source_file: Path, source_relative: Path):
        """Validate an internal link."""
        if link_url.startswith('../'):
            target_path = source_file.parent / link_url
        else:
            target_path = source_file.parent / link_url
        
        try:
            target_path = target_path.resolve()
            
            if not target_path.exists():
                self.errors.append(
                    f"Broken link in {source_relative}: {link_url} -> {target_path}"
                )
            elif not target_path.is_file():
                self.errors.append(
                    f"Link target is not a file in {source_relative}: {link_url}"
                )
        
        except Exception as e:
            self.errors.append(
                f"Error resolving link in {source_relative}: {link_url} ({str(e)})"
            )
    
    def _check_image_references(self):
        """Check image references in markdown files."""
        md_files = list(self.wiki_path.rglob("*.md"))
        
        for md_file in md_files:
            self._check_file_images(md_file)
    
    def _check_file_images(self, file_path: Path):
        """Check image references in a specific file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            relative_path = file_path.relative_to(self.wiki_path)
            
            img_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
            images = re.findall(img_pattern, content)
            
            for alt_text, img_url in images:
                if not img_url.startswith(('http://', 'https://')):
                    img_path = file_path.parent / img_url
                    if not img_path.exists():
                        self.warnings.append(
                            f"Missing image in {relative_path}: {img_url}"
                        )
        
        except Exception as e:
            self.errors.append(f"Error checking images in {relative_path}: {str(e)}")
    
    def _check_code_blocks(self):
        """Check code blocks for proper formatting."""
        md_files = list(self.wiki_path.rglob("*.md"))
        
        for md_file in md_files:
            self._check_file_code_blocks(md_file)
    
    def _check_file_code_blocks(self, file_path: Path):
        """Check code blocks in a specific file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            relative_path = file_path.relative_to(self.wiki_path)
            
            triple_backticks = content.count('```')
            
            if triple_backticks % 2 != 0:
                self.errors.append(
                    f"Unmatched code block markers in {relative_path}"
                )
        
        except Exception as e:
            self.errors.append(f"Error checking code blocks in {relative_path}: {str(e)}")
    
    def _report_results(self):
        """Report validation results."""
        print(f"\n📊 Validation Results:")
        print(f"   Errors: {len(self.errors)}")
        print(f"   Warnings: {len(self.warnings)}")
        
        if self.errors:
            print(f"\n❌ Errors:")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings:")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ Wiki validation passed with no issues!")
        elif not self.errors:
            print("\n✅ Wiki validation passed with warnings only.")
        else:
            print("\n❌ Wiki validation failed with errors.")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Validate COMET wiki structure")
    parser.add_argument(
        "--wiki-path",
        default="wiki",
        help="Path to wiki directory (default: wiki)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )
    
    args = parser.parse_args()
    
    validator = WikiValidator(args.wiki_path)
    success = validator.validate()
    
    if args.strict and validator.warnings:
        success = False
        print("\n⚠️  Strict mode: treating warnings as errors")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
