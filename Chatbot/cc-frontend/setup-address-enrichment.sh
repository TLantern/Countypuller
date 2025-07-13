#!/bin/bash

echo "==============================================="
echo "  ADDRESS ENRICHMENT SETUP (macOS/Linux)"
echo "==============================================="
echo ""

echo "This script will help you configure the environment variables"
echo "needed for automatic address enrichment during record pulling."
echo ""

echo "Required API Keys:"
echo ""
echo "1. SMARTYSTREETS_AUTH_ID and SMARTYSTREETS_AUTH_TOKEN"
echo "   - Get from https://www.smartystreets.com/"
echo "   - Sign up for SmartyStreets US Street API"
echo "   - Get your Auth ID and Auth Token from your dashboard"
echo "   - Provides the most accurate US address validation and ZIP+4"
echo ""
echo "2. GOOGLE_MAPS_API_KEY (Optional fallback)"
echo "   - Get from https://console.cloud.google.com/"
echo "   - Enable Geocoding API"
echo "   - Create credentials (API key)"
echo "   - Restrict to Geocoding API for security"
echo ""
echo "3. ATTOM_API_KEY (Required for property data)"
echo "   - Get from https://api.developer.attomdata.com/"
echo "   - Sign up for ATTOM Data API"
echo "   - Get your API key from the dashboard"
echo "   - Provides property valuations and loan data"
echo ""

echo "Choose setup method:"
echo "1. Add to current shell session (temporary)"
echo "2. Add to ~/.bash_profile (permanent for bash)"
echo "3. Add to ~/.zshrc (permanent for zsh)"
echo "4. Show manual export commands"
echo ""

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "Setting up temporary environment variables..."
        echo ""
        
        read -p "Enter your SMARTYSTREETS_AUTH_ID: " auth_id
        read -p "Enter your SMARTYSTREETS_AUTH_TOKEN: " auth_token
        read -p "Enter your ATTOM_API_KEY: " attom_key
        read -p "Enter your GOOGLE_MAPS_API_KEY (optional): " google_key
        
        export SMARTYSTREETS_AUTH_ID="$auth_id"
        export SMARTYSTREETS_AUTH_TOKEN="$auth_token"
        export ATTOM_API_KEY="$attom_key"
        
        if [ ! -z "$google_key" ]; then
            export GOOGLE_MAPS_API_KEY="$google_key"
        fi
        
        echo ""
        echo "✅ Environment variables set for current session!"
        echo "Note: These will be lost when you close the terminal."
        ;;
        
    2)
        echo ""
        echo "Adding to ~/.bash_profile..."
        echo ""
        
        read -p "Enter your SMARTYSTREETS_AUTH_ID: " auth_id
        read -p "Enter your SMARTYSTREETS_AUTH_TOKEN: " auth_token
        read -p "Enter your ATTOM_API_KEY: " attom_key
        read -p "Enter your GOOGLE_MAPS_API_KEY (optional): " google_key
        
        echo "" >> ~/.bash_profile
        echo "# Address Enrichment API Keys" >> ~/.bash_profile
        echo "export SMARTYSTREETS_AUTH_ID=\"$auth_id\"" >> ~/.bash_profile
        echo "export SMARTYSTREETS_AUTH_TOKEN=\"$auth_token\"" >> ~/.bash_profile
        echo "export ATTOM_API_KEY=\"$attom_key\"" >> ~/.bash_profile
        
        if [ ! -z "$google_key" ]; then
            echo "export GOOGLE_MAPS_API_KEY=\"$google_key\"" >> ~/.bash_profile
        fi
        
        echo ""
        echo "✅ Environment variables added to ~/.bash_profile!"
        echo "Run 'source ~/.bash_profile' or restart your terminal to apply changes."
        ;;
        
    3)
        echo ""
        echo "Adding to ~/.zshrc..."
        echo ""
        
        read -p "Enter your SMARTYSTREETS_AUTH_ID: " auth_id
        read -p "Enter your SMARTYSTREETS_AUTH_TOKEN: " auth_token
        read -p "Enter your ATTOM_API_KEY: " attom_key
        read -p "Enter your GOOGLE_MAPS_API_KEY (optional): " google_key
        
        echo "" >> ~/.zshrc
        echo "# Address Enrichment API Keys" >> ~/.zshrc
        echo "export SMARTYSTREETS_AUTH_ID=\"$auth_id\"" >> ~/.zshrc
        echo "export SMARTYSTREETS_AUTH_TOKEN=\"$auth_token\"" >> ~/.zshrc
        echo "export ATTOM_API_KEY=\"$attom_key\"" >> ~/.zshrc
        
        if [ ! -z "$google_key" ]; then
            echo "export GOOGLE_MAPS_API_KEY=\"$google_key\"" >> ~/.zshrc
        fi
        
        echo ""
        echo "✅ Environment variables added to ~/.zshrc!"
        echo "Run 'source ~/.zshrc' or restart your terminal to apply changes."
        ;;
        
    4)
        echo ""
        echo "Manual export commands:"
        echo ""
        echo "export SMARTYSTREETS_AUTH_ID=\"your_auth_id_here\""
        echo "export SMARTYSTREETS_AUTH_TOKEN=\"your_auth_token_here\""
        echo "export ATTOM_API_KEY=\"your_attom_api_key_here\""
        echo "export GOOGLE_MAPS_API_KEY=\"your_google_maps_key_here\"  # Optional"
        echo ""
        echo "Copy and paste these commands into your terminal,"
        echo "replacing the placeholder values with your actual API keys."
        ;;
        
    *)
        echo "Invalid choice. Please run the script again."
        exit 1
        ;;
esac

echo ""
echo "Next steps:"
echo "1. Test the setup by running the address enrichment pipeline"
echo "2. Pull records from the dashboard - they will now be automatically enriched"
echo "3. Check the logs for any API key issues"
echo ""
echo "For more information, see SMARTYSTREETS_SETUP.md"
echo ""
echo "Setup complete! 🎉" 