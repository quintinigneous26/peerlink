package main

import (
	"fmt"
	"log"

	"github.com/libp2p/go-libp2p"
)

func main() {
	// Create a basic libp2p host
	host, err := libp2p.New()
	if err != nil {
		log.Fatal(err)
	}
	defer host.Close()

	fmt.Printf("✅ libp2p host created successfully!\n")
	fmt.Printf("Peer ID: %s\n", host.ID())
	fmt.Printf("Addresses: %v\n", host.Addrs())
}
