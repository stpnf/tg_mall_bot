#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parser for Paveletskaya Plaza stores from 2GIS HTML
"""

import json
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

def parse_paveletskaya_stores(html_file: str) -> List[Dict]:
    """
    Parse stores from Paveletskaya Plaza HTML file
    
    Args:
        html_file: Path to the HTML file
        
    Returns:
        List of store dictionaries
    """
    
    # Read the HTML file
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    stores = []
    
    # Find all store containers
    store_containers = soup.find_all('div', class_='_1kf6gff')
    
    print(f"Found {len(store_containers)} store containers")
    
    for container in store_containers:
        store_data = {}
        
        # Extract store name
        name_link = container.find('a', class_='_1rehek')
        if name_link:
            name_span = name_link.find('span')
            if name_span:
                store_data['name'] = name_span.get_text(strip=True)
                
                # Extract store link
                store_data['link'] = name_link.get('href', '')
        
        # Extract store type
        type_span = container.find('span', class_='_oqoid')
        if type_span:
            store_data['type'] = type_span.get_text(strip=True)
        
        # Extract floor information
        floor_spans = container.find_all('span', class_='_sfdp8cg')
        floor_info = []
        for span in floor_spans:
            text = span.get_text(strip=True)
            if 'этаж' in text.lower():
                floor_info.append(text)
        if floor_info:
            store_data['floor'] = floor_info[0]  # Take the first floor mention
        
        # Extract rating
        rating_div = container.find('div', class_='_y10azs')
        if rating_div:
            rating_text = rating_div.get_text(strip=True)
            try:
                store_data['rating'] = float(rating_text)
            except ValueError:
                store_data['rating'] = rating_text
        
        # Extract review count
        reviews_div = container.find('div', class_='_jspzdm')
        if reviews_div:
            reviews_text = reviews_div.get_text(strip=True)
            # Extract number from text like "15 оценок"
            reviews_match = re.search(r'(\d+)', reviews_text)
            if reviews_match:
                store_data['reviews_count'] = int(reviews_match.group(1))
            else:
                store_data['reviews_count'] = reviews_text
        
        # Extract services/features
        services_div = container.find('div', class_='_4cxmw7')
        if services_div:
            services_text = services_div.get_text(strip=True)
            store_data['services'] = services_text
        
        # Extract additional description (if available)
        desc_div = container.find('div', class_='_snijgp')
        if desc_div:
            store_data['description'] = desc_div.get_text(strip=True)
        
        # Only add stores that have at least a name
        if store_data.get('name'):
            stores.append(store_data)
    
    return stores

def save_stores_to_json(stores: List[Dict], output_file: str):
    """
    Save stores data to JSON file
    
    Args:
        stores: List of store dictionaries
        output_file: Output JSON file path
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stores, f, ensure_ascii=False, indent=2)

def print_stores_summary(stores: List[Dict]):
    """
    Print summary of parsed stores
    
    Args:
        stores: List of store dictionaries
    """
    print(f"\n=== PAVELETSKAYA PLAZA STORES SUMMARY ===")
    print(f"Total stores found: {len(stores)}")
    
    # Count by floor
    floor_counts = {}
    for store in stores:
        floor = store.get('floor', 'Unknown')
        floor_counts[floor] = floor_counts.get(floor, 0) + 1
    
    print(f"\nStores by floor:")
    for floor, count in sorted(floor_counts.items()):
        print(f"  {floor}: {count} stores")
    
    # Count by type
    type_counts = {}
    for store in stores:
        store_type = store.get('type', 'Unknown')
        type_counts[store_type] = type_counts.get(store_type, 0) + 1
    
    print(f"\nTop store types:")
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    for store_type, count in sorted_types[:10]:
        print(f"  {store_type}: {count} stores")
    
    # Show some examples
    print(f"\nSample stores:")
    for i, store in enumerate(stores[:5]):
        print(f"  {i+1}. {store.get('name', 'Unknown')} - {store.get('type', 'Unknown')} - {store.get('floor', 'Unknown')}")

def main():
    """Main function"""
    input_file = "павелецкая плаза.txt"
    output_file = "paveletskaya_stores.json"
    
    try:
        print("Parsing Paveletskaya Plaza stores...")
        stores = parse_paveletskaya_stores(input_file)
        
        if stores:
            print(f"Successfully parsed {len(stores)} stores")
            
            # Save to JSON
            save_stores_to_json(stores, output_file)
            print(f"Stores saved to {output_file}")
            
            # Print summary
            print_stores_summary(stores)
            
            # Print first few stores as examples
            print(f"\n=== FIRST 10 STORES ===")
            for i, store in enumerate(stores[:10]):
                print(f"\n{i+1}. {store.get('name', 'Unknown')}")
                print(f"   Type: {store.get('type', 'Unknown')}")
                print(f"   Floor: {store.get('floor', 'Unknown')}")
                if store.get('rating'):
                    print(f"   Rating: {store.get('rating')} ({store.get('reviews_count', 'Unknown')} reviews)")
                if store.get('services'):
                    print(f"   Services: {store.get('services')}")
                if store.get('link'):
                    print(f"   Link: {store.get('link')}")
        else:
            print("No stores found!")
            
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found!")
    except Exception as e:
        print(f"Error parsing stores: {e}")

if __name__ == "__main__":
    main() 